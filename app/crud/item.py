import math
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, text
from app.models.item import (
    Item,
    ItemType,
    MeasureMethod,
    PartitionStat,
    LargeItemStat,
    ContainerStat,
    StockStatus,
    ItemStatHistory,
)
from app.models.partition import Partition
from app.models.large_item import LargeItem
from app.models.container import Container
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemStatsResponse
from app.utils.image import save_image_from_base64, delete_image, get_image_url
from typing import List, Optional, Tuple, Dict, Union

# Helper utilities
def _normalize_input_to_dict(obj: Union[ItemCreate, ItemUpdate, dict]) -> dict:
    if isinstance(obj, dict):
        return obj
    try:
        return obj.model_dump()
    except Exception:
        try:
            return obj.dict()
        except Exception:
            return {}

def _determine_stock_status(value: float, low_threshold, high_threshold) -> Optional[StockStatus]:
    if low_threshold is None and high_threshold is None:
        return None
    try:
        v = float(value or 0)
    except Exception:
        v = 0.0
    if high_threshold is not None and v >= float(high_threshold):
        return StockStatus.HIGH
    if low_threshold is not None and v <= float(low_threshold):
        return StockStatus.LOW
    return StockStatus.MEDIUM

def _persist_if_changed(db: Session, obj, changes: Dict, change_source: Optional[str] = None) -> None:
    changed = False
    changed_keys = []
    for k, v in changes.items():
        if getattr(obj, k) != v:
            setattr(obj, k, v)
            changed = True
            changed_keys.append(k)
    if changed:
        db.add(obj)
        # record history for stat rows if relevant fields changed
        try:
            _maybe_record_stat_history(db, obj, changed_keys, change_source)
        except Exception:
            # history recording must not block main update; swallow and continue
            db.rollback()
            # re-add obj after rollback so commit below can proceed
            db.add(obj)
        db.commit()
        db.refresh(obj)


def _maybe_record_stat_history(db: Session, stat_obj, changed_keys: list, change_source: Optional[str] = None) -> None:
    """
    Create ItemStatHistory snapshot when monitored stat fields changed.
    Only records for PartitionStat, LargeItemStat, ContainerStat and only when
    relevant fields changed.
    """
    # Determine monitored fields per stat type
    monitored = None
    payload = {}
    if isinstance(stat_obj, PartitionStat):
        monitored = {"total_quantity", "total_capacity", "stock_status"}
        if not monitored.intersection(changed_keys):
            return
        payload["total_quantity"] = getattr(stat_obj, "total_quantity", None)
        payload["total_capacity"] = getattr(stat_obj, "total_capacity", None)
        payload["total_weight"] = None
        payload["stock_status"] = getattr(stat_obj, "stock_status", None)
    elif isinstance(stat_obj, LargeItemStat):
        monitored = {"total_quantity", "stock_status"}
        if not monitored.intersection(changed_keys):
            return
        payload["total_quantity"] = getattr(stat_obj, "total_quantity", None)
        payload["total_capacity"] = None
        payload["total_weight"] = None
        payload["stock_status"] = getattr(stat_obj, "stock_status", None)
    elif isinstance(stat_obj, ContainerStat):
        monitored = {"total_weight", "total_quantity", "stock_status"}
        if not monitored.intersection(changed_keys):
            return
        payload["total_quantity"] = getattr(stat_obj, "total_quantity", None)
        payload["total_capacity"] = None
        payload["total_weight"] = getattr(stat_obj, "total_weight", None)
        payload["stock_status"] = getattr(stat_obj, "stock_status", None)
    else:
        return

    # Resolve item info
    item_row = db.query(Item).filter(Item.id == getattr(stat_obj, "item_id")).first()
    if not item_row:
        return

    hist = ItemStatHistory(
        item_id=item_row.id,
        item_name=item_row.name,
        item_type=item_row.item_type,
        total_quantity=payload.get("total_quantity"),
        total_capacity=payload.get("total_capacity"),
        total_weight=payload.get("total_weight"),
        stock_status=payload.get("stock_status"),
        change_source=change_source,
    )
    db.add(hist)

def _stat_status_value(stat_row):
    return stat_row.stock_status.value if getattr(stat_row, "stock_status", None) else None

# -- status updaters --
def _update_partition_status(db: Session, item_id: str, change_source: Optional[str] = None) -> None:
    ps = db.query(PartitionStat).filter(PartitionStat.item_id == item_id).first()
    if not ps:
        return
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    total_quantity = db.query(func.coalesce(func.sum(Partition.quantity), 0)).filter(Partition.item_id == item_id).scalar() or 0
    per_capacity = int(ps.partition_capacity) if ps.partition_capacity else 0
    total_capacity = int(partition_count) * per_capacity
    percent = (total_quantity / total_capacity) * 100.0 if total_capacity > 0 else 0.0
    new_status = _determine_stock_status(percent, ps.low_threshold, ps.high_threshold)
    _persist_if_changed(db, ps, {"total_quantity": int(total_quantity), "total_capacity": int(total_capacity), "stock_status": new_status}, change_source=change_source)

def _update_largeitem_status(db: Session, item_id: str, change_source: Optional[str] = None) -> None:
    ls = db.query(LargeItemStat).filter(LargeItemStat.item_id == item_id).first()
    if not ls:
        return
    total_qty = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    new_status = _determine_stock_status(total_qty, ls.low_threshold, ls.high_threshold)
    _persist_if_changed(db, ls, {"total_quantity": int(total_qty), "stock_status": new_status}, change_source=change_source)

def _update_container_status(db: Session, item_id: str, change_source: Optional[str] = None) -> None:
    cs = db.query(ContainerStat).filter(ContainerStat.item_id == item_id).first()
    if not cs:
        return
    total_weight = db.query(func.coalesce(func.sum(Container.items_weight), 0.0)).filter(Container.item_id == item_id).scalar() or 0.0
    computed_total_quantity = None
    if cs.container_item_weight is not None and cs.container_item_weight > 0:
        try:
            computed_total_quantity = int(round(total_weight / float(cs.container_item_weight)))
        except Exception:
            computed_total_quantity = 0
    new_status = _determine_stock_status(total_weight, cs.low_threshold, cs.high_threshold)
    changes = {"total_weight": float(total_weight), "stock_status": new_status}
    changes["total_quantity"] = computed_total_quantity if cs.container_item_weight is not None else None
    _persist_if_changed(db, cs, changes, change_source=change_source)

# -- stats readers --
def get_partition_stats(db: Session, item_id: str) -> Dict[str, int]:
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    total_quantity = db.query(func.coalesce(func.sum(Partition.quantity), 0)).filter(Partition.item_id == item_id).scalar() or 0
    ps = db.query(PartitionStat).filter(PartitionStat.item_id == item_id).first()
    per_capacity = int(ps.partition_capacity) if ps and ps.partition_capacity else 0
    total_capacity = int(partition_count) * per_capacity
    return {"partition_count": int(partition_count), "total_quantity": int(total_quantity), "total_capacity": int(total_capacity)}

def get_large_item_stats(db: Session, item_id: str) -> Dict[str, int]:
    large_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    return {"large_item_count": int(large_count), "total_quantity": int(large_count)}

def get_container_stats(db: Session, item_id: str) -> Dict[str, object]:
    container_count = db.query(func.count(Container.id)).filter(Container.item_id == item_id).scalar() or 0
    total_weight = db.query(func.coalesce(func.sum(Container.items_weight), 0.0)).filter(Container.item_id == item_id).scalar() or 0.0
    total_quantity = db.query(func.coalesce(func.sum(Container.quantity), 0)).filter(Container.item_id == item_id).scalar() or 0
    cs = db.query(ContainerStat).filter(ContainerStat.item_id == item_id).first()
    exposed_total_quantity = int(total_quantity) if (cs and cs.container_item_weight) else None
    return {"container_count": int(container_count), "total_weight": float(total_weight), "total_quantity": exposed_total_quantity}

# -- response builders --
def _to_dict_safe(pydantic_obj):
    try:
        return pydantic_obj.model_dump()
    except Exception:
        try:
            return pydantic_obj.dict()
        except Exception:
            return pydantic_obj

def create_item_response(db: Session, item: Item, base_url: str = "") -> ItemResponse:

    try:
        db.refresh(item)
    except Exception:
        pass

    image_url = get_image_url(item.id, base_url) if item.image_path else None

    partition_stat = None
    largeitem_stat = None
    container_stat = None
    partitions_list = None

    if getattr(item, "partition_stat", None):
        ps = item.partition_stat
        partition_stat = {
            "total_quantity": ps.total_quantity,
            "total_capacity": ps.total_capacity,
            "partition_capacity": ps.partition_capacity,
            "high_threshold": ps.high_threshold,
            "low_threshold": ps.low_threshold,
            "stock_status": _stat_status_value(ps)
        }

    if getattr(item, "largeitem_stat", None):
        ls = item.largeitem_stat
        largeitem_stat = {
            "total_quantity": ls.total_quantity,
            "high_threshold": ls.high_threshold,
            "low_threshold": ls.low_threshold,
            "stock_status": _stat_status_value(ls)
        }

    if getattr(item, "container_stat", None):
        cs = item.container_stat
        container_stat = {
            "container_item_weight": cs.container_item_weight,
            "container_weight": cs.container_weight,
            "total_weight": cs.total_weight,
            "total_quantity": cs.total_quantity,
            "high_threshold": cs.high_threshold,
            "low_threshold": cs.low_threshold,
            "stock_status": _stat_status_value(cs)
        }

    if item.item_type == ItemType.PARTITION:
        partitions = db.query(Partition).filter(Partition.item_id == item.id).order_by(Partition.id).all()
        partitions_list = [
            {
                "id": p.id,
                "storage_section_id": p.storage_section_id,
                "rfid_tag_id": p.rfid_tag_id,
                "quantity": p.quantity,
                "status": getattr(getattr(p, "status", None), "value", p.status)
            } for p in partitions
        ]

    return ItemResponse.model_validate({
        "id": item.id,
        "name": item.name,
        "manufacturer": item.manufacturer,
        "item_type": item.item_type.value if getattr(item, "item_type", None) is not None else None,
        "measure_method": item.measure_method.value if getattr(item, "measure_method", None) is not None else None,
        "image_url": image_url,
        "process": item.process,
        "tooling_used": item.tooling_used,
        "vendor_pn": item.vendor_pn,
        "sap_pn": item.sap_pn,
        "package_used": item.package_used,
        "partition_stat": partition_stat,
        "largeitem_stat": largeitem_stat,
        "container_stat": container_stat,
        "partitions": partitions_list,
    })

def build_item_with_stats(db: Session, item: Item, base_url: str) -> ItemStatsResponse:
    item_response = create_item_response(db, item, base_url)
    base_data = _to_dict_safe(item_response)

    stats = {}
    if item.item_type == ItemType.PARTITION:
        p = get_partition_stats(db, item.id)
        ps_row = db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first()
        stats = {
            "partition_count": p.get("partition_count", 0),
            "stock_status": _stat_status_value(ps_row)
        }
    elif item.item_type == ItemType.LARGE_ITEM:
        ls = db.query(LargeItemStat).filter(LargeItemStat.item_id == item.id).first()
        stats = {"stock_status": _stat_status_value(ls)}
    elif item.item_type == ItemType.CONTAINER:
        c = get_container_stats(db, item.id)
        cs = db.query(ContainerStat).filter(ContainerStat.item_id == item.id).first()
        stats = {
            "container_count": c.get("container_count", 0),
            "stock_status": _stat_status_value(cs)
        }

    merged = {**base_data, **stats}
    return ItemStatsResponse.model_validate(merged)

def get_item(db: Session, item_id: str) -> Optional[Item]:
    return db.query(Item).filter(Item.id == item_id).first()

def get_items(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    item_type: Optional[ItemType] = None,
    manufacturer: Optional[str] = None,
    stock_status: Optional[str] = None
) -> Tuple[List[Item], int]:
    query = db.query(Item)
    if search:
        search_term = f"%{search}%"
        query = query.filter(or_(Item.id.ilike(search_term), Item.name.ilike(search_term), Item.manufacturer.ilike(search_term)))
    if item_type:
        query = query.filter(Item.item_type == item_type)
    if manufacturer:
        query = query.filter(Item.manufacturer.ilike(f"%{manufacturer}%"))

    # Apply stock_status filter if provided. Matches items whose per-type stat row
    # has the requested stock_status (partition / large_item / container).
    if stock_status:
        ss_enum = None
        try:
            ss_enum = StockStatus(stock_status)
        except Exception:
            # Try case-insensitive match then fail with clear message
            try:
                ss_enum = StockStatus(stock_status.upper())
            except Exception:
                raise ValueError({"field": "stock_status", "message": f"Invalid stock_status. Must be one of {[s.value for s in StockStatus]}"})

        status_cond = or_(
            and_(
                Item.item_type == ItemType.PARTITION,
                db.query(PartitionStat).filter(PartitionStat.item_id == Item.id, PartitionStat.stock_status == ss_enum).exists()
            ),
            and_(
                Item.item_type == ItemType.LARGE_ITEM,
                db.query(LargeItemStat).filter(LargeItemStat.item_id == Item.id, LargeItemStat.stock_status == ss_enum).exists()
            ),
            and_(
                Item.item_type == ItemType.CONTAINER,
                db.query(ContainerStat).filter(ContainerStat.item_id == Item.id, ContainerStat.stock_status == ss_enum).exists()
            ),
        )
        query = query.filter(status_cond)

    query = query.order_by(Item.id)
    total_count = query.count()
    skip = (page - 1) * page_size
    items = query.offset(skip).limit(page_size).all()
    return items, total_count

def _create_initial_stat_for_item(db: Session, db_item: Item, data: dict) -> None:
    if db_item.item_type == ItemType.PARTITION:
        if not db.query(PartitionStat).filter(PartitionStat.item_id == db_item.id).first():
            ps = PartitionStat(item_id=db_item.id, total_quantity=0, total_capacity=0,
                               partition_capacity=data.get("partition_capacity"),
                               high_threshold=data.get("partition_high"),
                               low_threshold=data.get("partition_low"),
                               stock_status=StockStatus.LOW)
            db.add(ps)
            db.flush()
    elif db_item.item_type == ItemType.LARGE_ITEM:
        if not db.query(LargeItemStat).filter(LargeItemStat.item_id == db_item.id).first():
            ls = LargeItemStat(item_id=db_item.id, total_quantity=0,
                               high_threshold=data.get("large_high"),
                               low_threshold=data.get("large_low"),
                               stock_status=StockStatus.LOW)
            db.add(ls)
            db.flush()
    elif db_item.item_type == ItemType.CONTAINER:
        if not db.query(ContainerStat).filter(ContainerStat.item_id == db_item.id).first():
            init_total_qty = 0 if data.get("container_item_weight") is not None else None
            cs = ContainerStat(item_id=db_item.id,
                               container_item_weight=data.get("container_item_weight"),
                               container_weight=data.get("container_weight"),
                               total_weight=0.0,
                               total_quantity=init_total_qty,
                               high_threshold=data.get("container_high"),
                               low_threshold=data.get("container_low"),
                               stock_status=StockStatus.LOW)
            db.add(cs)
            db.flush()

def create_item(db: Session, item: Union[ItemCreate, dict]) -> Item:
    data = _normalize_input_to_dict(item)
    # convert item_type if string
    itype = data.get("item_type")
    if isinstance(itype, str):
        itype = ItemType(itype)
        data["item_type"] = itype
    _ensure_thresholds_valid(data, effective_item_type=itype)

    item_id = data.get("id")
    if item_id and get_item(db, item_id):
        raise ValueError({"field": "id", "message": "Item with this ID already exists"})

    image_b64 = data.get("image")
    image_path = None
    if image_b64:
        if not item_id:
            raise ValueError({"field": "id", "message": "id is required when sending image"})
        image_path = save_image_from_base64(item_id, image_b64)

    mmethod = data.get("measure_method")
    if isinstance(mmethod, str):
        mmethod = MeasureMethod(mmethod)

    db_item = Item(
        id=item_id,
        name=data.get("name"),
        manufacturer=data.get("manufacturer"),
        item_type=itype,
        measure_method=mmethod,
        image_path=image_path,
        process=data.get("process"),
        tooling_used=data.get("tooling_used"),
        vendor_pn=data.get("vendor_pn"),
        sap_pn=data.get("sap_pn"),
        package_used=data.get("package_used"),
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    try:
        _create_initial_stat_for_item(db, db_item, data)
        db.commit()
        db.refresh(db_item)
    except Exception:
        db.rollback()
        raise

    return db_item

def update_item(db: Session, item_id: str, item: Union[ItemUpdate, dict]) -> Optional[Item]:
    db_item = get_item(db, item_id)
    if not db_item:
        return None

    # remember original type so we can remove its stat row if the type changes
    original_type = db_item.item_type

    update_data = _normalize_input_to_dict(item)
    # if incoming contains item_type string convert
    if "item_type" in update_data and isinstance(update_data["item_type"], str):
        update_data["item_type"] = ItemType(update_data["item_type"])

    # enforce thresholds for the effective type (existing or newly set)
    effective_type = update_data.get("item_type") or db_item.item_type
    _ensure_thresholds_valid(update_data, effective_item_type=effective_type)

    # extract stat-specific inputs
    partition_capacity_val = update_data.pop("partition_capacity", None)
    partition_high = update_data.pop("partition_high", None)
    partition_low = update_data.pop("partition_low", None)
    partition_stock_status = update_data.pop("partition_stock_status", None)

    large_high = update_data.pop("large_high", None)
    large_low = update_data.pop("large_low", None)
    large_stock_status = update_data.pop("large_stock_status", None)

    container_item_weight_val = update_data.pop("container_item_weight", None)
    container_weight_val = update_data.pop("container_weight", None)
    container_high = update_data.pop("container_high", None)
    container_low = update_data.pop("container_low", None)
    container_stock_status = update_data.pop("container_stock_status", None)

    # normalize enums present
    if "measure_method" in update_data and isinstance(update_data["measure_method"], str):
        update_data["measure_method"] = MeasureMethod(update_data["measure_method"])

    # image handling
    if "image" in update_data:
        image_value = update_data.pop("image")
        if db_item.image_path:
            delete_image(db_item.image_path)
        if image_value is None:
            db_item.image_path = None
        else:
            db_item.image_path = save_image_from_base64(db_item.id, image_value)

    # apply remaining item-level attributes
    for key, value in update_data.items():
        setattr(db_item, key, value)

    # enforce measure_method by type
    if db_item.item_type == ItemType.PARTITION:
        db_item.measure_method = MeasureMethod.VISION
    elif db_item.item_type == ItemType.LARGE_ITEM:
        db_item.measure_method = None
    elif db_item.item_type == ItemType.CONTAINER:
        db_item.measure_method = MeasureMethod.WEIGHT

    # If the item_type changed, remove the old stat row so state stays consistent.
    if original_type != db_item.item_type:
        if original_type == ItemType.PARTITION:
            db.query(PartitionStat).filter(PartitionStat.item_id == db_item.id).delete(synchronize_session=False)
        elif original_type == ItemType.LARGE_ITEM:
            db.query(LargeItemStat).filter(LargeItemStat.item_id == db_item.id).delete(synchronize_session=False)
        elif original_type == ItemType.CONTAINER:
            db.query(ContainerStat).filter(ContainerStat.item_id == db_item.id).delete(synchronize_session=False)
        # commit deletion together with the item changes below
    db.commit()
    db.refresh(db_item)

    # upsert per-type stat rows
    if db_item.item_type == ItemType.PARTITION:
        ps = db.query(PartitionStat).filter(PartitionStat.item_id == db_item.id).first()
        if not ps:
            ps = PartitionStat(item_id=db_item.id, total_quantity=0)
            db.add(ps)
        if partition_capacity_val is not None:
            ps.partition_capacity = partition_capacity_val
        if partition_high is not None:
            ps.high_threshold = partition_high
        if partition_low is not None:
            ps.low_threshold = partition_low
        if partition_stock_status is not None:
            ps.stock_status = StockStatus(partition_stock_status)
        db.commit()
        db.refresh(ps)

    if db_item.item_type == ItemType.LARGE_ITEM:
        ls = db.query(LargeItemStat).filter(LargeItemStat.item_id == db_item.id).first()
        if not ls:
            ls = LargeItemStat(item_id=db_item.id, total_quantity=0)
            db.add(ls)
        if large_high is not None:
            ls.high_threshold = large_high
        if large_low is not None:
            ls.low_threshold = large_low
        if large_stock_status is not None:
            ls.stock_status = StockStatus(large_stock_status)
        db.commit()
        db.refresh(ls)

    if db_item.item_type == ItemType.CONTAINER:
        cs = db.query(ContainerStat).filter(ContainerStat.item_id == db_item.id).first()
        if not cs:
            cs = ContainerStat(item_id=db_item.id, total_weight=0.0)
            db.add(cs)

        if "container_item_weight_val" in locals():
            cs.container_item_weight = container_item_weight_val

        if container_weight_val is not None:
            cs.container_weight = container_weight_val

        if container_high is not None:
            cs.high_threshold = container_high

        if container_low is not None:
            cs.low_threshold = container_low

        if container_stock_status is not None:
            cs.stock_status = StockStatus(container_stock_status)

        db.commit()
        db.refresh(cs)

    # recompute statuses
    if db_item.item_type == ItemType.PARTITION:
        _update_partition_status(db, db_item.id, "Item Threshold Change")    
    if db_item.item_type == ItemType.LARGE_ITEM:
        _update_largeitem_status(db, db_item.id, "Item Threshold Change")
    if db_item.item_type == ItemType.CONTAINER:
        _update_container_status(db, db_item.id, "Item Threshold Change")

    return db_item

def delete_item(db: Session, item_id: str) -> Optional[Item]:
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    if db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() > 0 \
       or db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() > 0 \
       or db.query(func.count(Container.id)).filter(Container.item_id == item_id).scalar() > 0:
        raise ValueError({"field": "item_id", "message": "Cannot delete item with associated partitions, large items, or containers"})
    if db_item.image_path:
        delete_image(db_item.image_path)
    db.delete(db_item)
    db.commit()
    return db_item

def search_items_by_keyword(db: Session, keyword: str, limit: int = 20) -> List[Item]:
    search_term = f"%{keyword}%"
    return db.query(Item).filter(or_(Item.id.ilike(search_term), Item.name.ilike(search_term), Item.manufacturer.ilike(search_term))).limit(limit).all()

def get_items_by_type(db: Session, item_type: ItemType) -> List[Item]:
    return db.query(Item).filter(Item.item_type == item_type).order_by(Item.name).all()

def get_items_by_manufacturer(db: Session, manufacturer: str) -> List[Item]:
    return db.query(Item).filter(Item.manufacturer.ilike(f"%{manufacturer}%")).order_by(Item.name).all()

def get_item_count(db: Session) -> int:
    return db.query(Item).count()

def get_item_count_by_type(db: Session, item_type: ItemType) -> int:
    return db.query(Item).filter(Item.item_type == item_type).count()

def get_manufacturer_count(db: Session) -> int:
    return db.query(func.count(func.distinct(Item.manufacturer))).scalar() or 0

def _ensure_thresholds_valid(data: dict, effective_item_type: Optional[Union[ItemType, str]] = None) -> None:
    """
    Enforce thresholds. effective_item_type (ItemType or str) is the item type we must validate for.
    Thresholds are mandatory for the effective type.
    """
    # normalize effective type to ItemType if possible
    eit = effective_item_type
    if isinstance(eit, str):
        try:
            eit = ItemType(eit)
        except Exception:
            eit = None

    def _as_float(val, name):
        try:
            return None if val is None else float(val)
        except Exception:
            raise ValueError({"field": name, "message": f"{name} must be a number"})

    # partition thresholds must be percentages 0..100 and required for partition type
    ph = _as_float(data.get("partition_high"), "partition_high")
    pl = _as_float(data.get("partition_low"), "partition_low")
    for v, n in ((ph, "partition_high"), (pl, "partition_low")):
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError({"field": n, "message": f"{n} must be between 0 and 100"})
    if ph is not None and pl is not None and not (ph > pl):
        raise ValueError({"field": "partition_high/low", "message": "partition_high must be greater than partition_low"})
    if eit == ItemType.PARTITION:
        if ph is None or pl is None:
            raise ValueError({"field": "partition_high/low", "message": "partition_high and partition_low are required for partition items"})

    # large_item thresholds (integers) and required for large_item type
    lh = data.get("large_high")
    ll = data.get("large_low")
    if lh is not None and ll is not None and not (int(lh) > int(ll)):
        raise ValueError({"field": "large_high/low", "message": "large_high must be greater than large_low"})
    if eit == ItemType.LARGE_ITEM:
        if lh is None or ll is None:
            raise ValueError({"field": "large_high/low", "message": "large_high and large_low are required for large_item items"})

    # container thresholds (floats) and required for container type
    ch = data.get("container_high")
    cl = data.get("container_low")
    if ch is not None and cl is not None and not (float(ch) > float(cl)):
        raise ValueError({"field": "container_high/low", "message": "container_high must be greater than container_low"})
    if eit == ItemType.CONTAINER:
        if ch is None or cl is None:
            raise ValueError({"field": "container_high/low", "message": "container_high and container_low are required for container items"})

def get_items_overview(db: Session):
    # --- total items ---
    total_items = db.query(func.count(Item.id)).scalar() or 0

    # --- count of registered units (from actual physical tables) ---
    partitions_count = db.query(func.count(Partition.id)).scalar() or 0
    large_items_count = db.query(func.count(LargeItem.id)).scalar() or 0
    containers_count = db.query(func.count(Container.id)).scalar() or 0
    total_units = partitions_count + large_items_count + containers_count

    # --- helper to count stock status for each stat table ---
    def stock_count(model, status):
        return db.query(func.count(model.item_id)).filter(model.stock_status == status).scalar() or 0

    # --- stock breakdown (combine across all stat tables) ---
    low = (
        stock_count(PartitionStat, StockStatus.LOW)
        + stock_count(LargeItemStat, StockStatus.LOW)
        + stock_count(ContainerStat, StockStatus.LOW)
    )

    medium = (
        stock_count(PartitionStat, StockStatus.MEDIUM)
        + stock_count(LargeItemStat, StockStatus.MEDIUM)
        + stock_count(ContainerStat, StockStatus.MEDIUM)
    )

    high = (
        stock_count(PartitionStat, StockStatus.HIGH)
        + stock_count(LargeItemStat, StockStatus.HIGH)
        + stock_count(ContainerStat, StockStatus.HIGH)
    )

    # --- result ---
    return {
        "total_items": total_items,
        "total_units": total_units,
        "units_breakdown": {
            "partitions": partitions_count,
            "large_items": large_items_count,
            "containers": containers_count,
        },
        "stock": {
            "low": low,
            "medium": medium,
            "high": high,
        },
    }