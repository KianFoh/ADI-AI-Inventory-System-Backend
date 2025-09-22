from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.item import Item, ItemType, MeasureMethod, PartitionStat, LargeItemStat, ContainerStat, StockStatus
from app.models.partition import Partition
from app.models.large_item import LargeItem
from app.models.container import Container
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemStatsResponse
from app.utils.image import save_image_from_base64, delete_image, get_image_url
from typing import List, Optional, Tuple, Dict, Union

# Helper utilities
def _normalize_input_to_dict(obj: Union[ItemCreate, ItemUpdate, dict]) -> dict:
    """Normalize Pydantic model or dict to plain dict safely."""
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
    """Return StockStatus based on numeric value and thresholds. None if no thresholds."""
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

def _persist_if_changed(db: Session, obj, changes: Dict) -> None:
    """Set attributes from changes dict on obj and persist only if any change detected."""
    changed = False
    for k, v in changes.items():
        if getattr(obj, k) != v:
            setattr(obj, k, v)
            changed = True
    if changed:
        db.add(obj)
        db.commit()
        db.refresh(obj)

# -- status updaters (clean, deterministic) --
def _update_partition_status(db: Session, item_id: str) -> None:
    """Update PartitionStat totals + stock_status from Partition rows."""
    ps = db.query(PartitionStat).filter(PartitionStat.item_id == item_id).first()
    if not ps:
        return
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    total_quantity = db.query(func.coalesce(func.sum(Partition.quantity), 0)).filter(Partition.item_id == item_id).scalar() or 0
    per_capacity = int(ps.partition_capacity) if ps.partition_capacity else 0
    total_capacity = int(partition_count) * per_capacity
    percent = (total_quantity / total_capacity) * 100.0 if total_capacity > 0 else 0.0
    new_status = _determine_stock_status(percent, ps.low_threshold, ps.high_threshold)

    _persist_if_changed(db, ps, {
        "total_quantity": int(total_quantity),
        "total_capacity": int(total_capacity),
        "stock_status": new_status
    })

def _update_largeitem_status(db: Session, item_id: str) -> None:
    """Update LargeItemStat.total_quantity and stock_status from LargeItem rows."""
    ls = db.query(LargeItemStat).filter(LargeItemStat.item_id == item_id).first()
    if not ls:
        return
    total_qty = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    new_status = _determine_stock_status(total_qty, ls.low_threshold, ls.high_threshold)

    _persist_if_changed(db, ls, {
        "total_quantity": int(total_qty),
        "stock_status": new_status
    })

def _update_container_status(db: Session, item_id: str) -> None:
    """Update ContainerStat.total_weight/total_quantity and stock_status from Container rows."""
    cs = db.query(ContainerStat).filter(ContainerStat.item_id == item_id).first()
    if not cs:
        return
    total_weight = db.query(func.coalesce(func.sum(Container.items_weight), 0.0)).filter(Container.item_id == item_id).scalar() or 0.0

    computed_total_quantity = None
    if cs.container_item_weight is not None and cs.container_item_weight > 0:
        try:
            computed_total_quantity = int(total_weight / float(cs.container_item_weight))
        except Exception:
            computed_total_quantity = 0

    new_status = _determine_stock_status(total_weight, cs.low_threshold, cs.high_threshold)

    changes = {"total_weight": float(total_weight), "stock_status": new_status}
    # total_quantity only meaningful when container_item_weight configured
    if cs.container_item_weight is not None:
        changes["total_quantity"] = computed_total_quantity
    else:
        changes["total_quantity"] = None

    _persist_if_changed(db, cs, changes)

# -- stats readers --
def get_partition_stats(db: Session, item_id: str) -> Dict[str, int]:
    from app.models.partition import Partition
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    total_quantity = db.query(func.coalesce(func.sum(Partition.quantity), 0)).filter(Partition.item_id == item_id).scalar() or 0
    ps = db.query(PartitionStat).filter(PartitionStat.item_id == item_id).first()
    per_capacity = int(ps.partition_capacity) if ps and ps.partition_capacity else 0
    total_capacity = int(partition_count) * per_capacity
    return {"partition_count": int(partition_count), "total_quantity": int(total_quantity), "total_capacity": int(total_capacity)}

def get_large_item_stats(db: Session, item_id: str) -> Dict[str, int]:
    from app.models.large_item import LargeItem
    large_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    return {"large_item_count": int(large_count), "total_quantity": int(large_count)}

def get_container_stats(db: Session, item_id: str) -> Dict[str, object]:
    from app.models.container import Container
    container_count = db.query(func.count(Container.id)).filter(Container.item_id == item_id).scalar() or 0
    total_weight = db.query(func.coalesce(func.sum(Container.items_weight), 0.0)).filter(Container.item_id == item_id).scalar() or 0.0
    total_quantity = db.query(func.coalesce(func.sum(Container.quantity), 0)).filter(Container.item_id == item_id).scalar() or 0
    cs = db.query(ContainerStat).filter(ContainerStat.item_id == item_id).first()
    exposed_total_quantity = int(total_quantity) if (cs and cs.container_item_weight) else None
    return {"container_count": int(container_count), "total_weight": float(total_weight), "total_quantity": exposed_total_quantity}

# -- response builders --
def create_item_response(db: Session, item: Item, base_url: str = "") -> ItemResponse:
    """Return ItemResponse with up-to-date backend-calculated stats (no client-provided totals)."""
    if item.item_type == ItemType.PARTITION:
        _update_partition_status(db, item.id)
    elif item.item_type == ItemType.LARGE_ITEM:
        _update_largeitem_status(db, item.id)
    elif item.item_type == ItemType.CONTAINER:
        _update_container_status(db, item.id)

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
            "stock_status": ps.stock_status.value if getattr(ps, "stock_status", None) else None
        }

    if getattr(item, "largeitem_stat", None):
        ls = item.largeitem_stat
        largeitem_stat = {
            "total_quantity": ls.total_quantity,
            "high_threshold": ls.high_threshold,
            "low_threshold": ls.low_threshold,
            "stock_status": ls.stock_status.value if getattr(ls, "stock_status", None) else None
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
            "stock_status": cs.stock_status.value if getattr(cs, "stock_status", None) else None
        }

    # include partition rows when item is partition type
    if item.item_type == ItemType.PARTITION:
        from app.models.partition import Partition
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
    """Return ItemStatsResponse combining create_item_response and aggregated counts."""
    item_response = create_item_response(db, item, base_url)
    base_data = _to_dict_safe(item_response)

    # counts aggregated from rows
    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    from app.models.container import Container
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item.id).scalar() or 0
    large_item_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item.id).scalar() or 0
    container_count = db.query(func.count(Container.id)).filter(Container.item_id == item.id).scalar() or 0
    total_instances = partition_count + large_item_count + container_count

    # per-type stats
    stats = {}
    if item.item_type == ItemType.PARTITION:
        p = get_partition_stats(db, item.id)
        stats = {
            "total_quantity": p["total_quantity"],
            "total_capacity": p["total_capacity"],
            "partition_count": p["partition_count"],
            "stock_status": (db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first().stock_status.value
                             if db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first() and
                                db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first().stock_status else None)
        }
    elif item.item_type == ItemType.LARGE_ITEM:
        ls = db.query(LargeItemStat).filter(LargeItemStat.item_id == item.id).first()
        stats = {"stock_status": ls.stock_status.value if ls and ls.stock_status else None}
    elif item.item_type == ItemType.CONTAINER:
        c = get_container_stats(db, item.id)
        cs = db.query(ContainerStat).filter(ContainerStat.item_id == item.id).first()
        stats = {
            "total_weight": c.get("total_weight", 0.0),
            "container_count": c.get("container_count", 0),
            "stock_status": cs.stock_status.value if cs and cs.stock_status else None
        }
        if cs and cs.container_item_weight:
            stats["total_quantity"] = c.get("total_quantity", 0)

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
    manufacturer: Optional[str] = None
) -> Tuple[List[Item], int]:
    query = db.query(Item)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Item.id.ilike(search_term),
                Item.name.ilike(search_term),
                Item.manufacturer.ilike(search_term)
            )
        )
    
    if item_type:
        query = query.filter(Item.item_type == item_type)
    
    if manufacturer:
        query = query.filter(Item.manufacturer.ilike(f"%{manufacturer}%"))
    
    query = query.order_by(Item.id)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    items = query.offset(skip).limit(page_size).all()
    
    return items, total_count

def _create_initial_stat_for_item(db: Session, db_item: Item, data: dict) -> None:
    """Create per-type stat row. Totals are initialized by backend and not taken from client data."""
    if db_item.item_type == ItemType.PARTITION:
        if not db.query(PartitionStat).filter(PartitionStat.item_id == db_item.id).first():
            ps = PartitionStat(
                item_id=db_item.id,
                total_quantity=0,           # backend starts at 0
                total_capacity=0,           # backend-managed computed value
                partition_capacity=data.get("partition_capacity"),
                high_threshold=data.get("partition_high"),
                low_threshold=data.get("partition_low"),
                stock_status=None
            )
            db.add(ps)
            db.flush()
            _update_partition_status(db, db_item.id)
    elif db_item.item_type == ItemType.LARGE_ITEM:
        if not db.query(LargeItemStat).filter(LargeItemStat.item_id == db_item.id).first():
            ls = LargeItemStat(
                item_id=db_item.id,
                total_quantity=0,           # backend-managed
                high_threshold=data.get("large_high"),
                low_threshold=data.get("large_low"),
                stock_status=None
            )
            db.add(ls)
            db.flush()
            _update_largeitem_status(db, db_item.id)
    elif db_item.item_type == ItemType.CONTAINER:
        if not db.query(ContainerStat).filter(ContainerStat.item_id == db_item.id).first():
            init_total_qty = 0 if data.get("container_item_weight") is not None else None
            cs = ContainerStat(
                item_id=db_item.id,
                container_item_weight=data.get("container_item_weight"),
                container_weight=data.get("container_weight"),
                total_weight=0.0,           # backend starts at 0
                total_quantity=init_total_qty,
                high_threshold=data.get("container_high"),
                low_threshold=data.get("container_low"),
                stock_status=None
            )
            db.add(cs)
            db.flush()
            _update_container_status(db, db_item.id)

def create_item(db: Session, item: Union[ItemCreate, dict]) -> Item:
    """Create new item with validation and image support. Accepts ItemCreate or dict."""

    data = _normalize_input_to_dict(item)

    # validate thresholds (ranges, ordering, required for type)
    _ensure_thresholds_valid(data)
    
    # ensure required id/name etc present
    item_id = data.get("id")
    if item_id and get_item(db, item_id):
        raise ValueError({"field": "id", "message": "Item with this ID already exists"})

    # save image if provided (image is base64 string)
    image_b64 = data.get("image")
    image_path = None
    if image_b64:
        # if id not provided yet, db id must exist; require id in payload
        if not item_id:
            raise ValueError({"field": "id", "message": "id is required when sending image"})
        image_path = save_image_from_base64(item_id, image_b64)

    # normalize/convert enums if they are string values
    itype = data.get("item_type")
    if isinstance(itype, str):
        itype = ItemType(itype)  # will raise if invalid
    mmethod = data.get("measure_method")
    if isinstance(mmethod, str):
        mmethod = MeasureMethod(mmethod)

    # build SQLAlchemy model instance including new fields
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

    # create per-type stat row using provided inputs (partition_capacity/container weights)
    try:
        _create_initial_stat_for_item(db, db_item, data)
        db.commit()
        db.refresh(db_item)
    except Exception:
        db.rollback()
        raise

    return db_item

def update_item(db: Session, item_id: str, item: Union[ItemUpdate, dict]) -> Optional[Item]:
    """Update item with type-specific validation. Accepts ItemUpdate or dict."""


    db_item = get_item(db, item_id)
    if not db_item:
        return None

    update_data = _normalize_input_to_dict(item)

    # validate thresholds in the incoming update payload (if present)
    _ensure_thresholds_valid(update_data)
    
    # --- extract stat-specific inputs so they are not set on Item columns ---
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
    # ---------------------------------------------------------------------


    # normalize enum strings if present
    if "item_type" in update_data and isinstance(update_data["item_type"], str):
        update_data["item_type"] = ItemType(update_data["item_type"])
    if "measure_method" in update_data and isinstance(update_data["measure_method"], str):
        update_data["measure_method"] = MeasureMethod(update_data["measure_method"])

    # image handling
    if 'image' in update_data:
        image_value = update_data.pop('image')
        if db_item.image_path:
            delete_image(db_item.image_path)
        if image_value is None:
            db_item.image_path = None
        else:
            db_item.image_path = save_image_from_base64(db_item.id, image_value)

    # assign remaining Item-level fields
    for key, value in update_data.items():
        setattr(db_item, key, value)

    # enforce type-specific validation on Item
    if db_item.item_type == ItemType.PARTITION:
        db_item.measure_method = MeasureMethod.VISION
    elif db_item.item_type == ItemType.LARGE_ITEM:
        db_item.measure_method = None
    elif db_item.item_type == ItemType.CONTAINER:
        db_item.measure_method = MeasureMethod.WEIGHT

    db.commit()
    db.refresh(db_item)

    # --- Upsert per-type stat values if provided ---
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
        if container_item_weight_val is not None:
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
    # ---------------------------------------------------------------------

    # After stat upserts, recompute statuses to reflect new thresholds / capacities
    if db_item.item_type == ItemType.PARTITION:
        _update_partition_status(db, db_item.id)
    if db_item.item_type == ItemType.LARGE_ITEM:
        _update_largeitem_status(db, db_item.id)
    if db_item.item_type == ItemType.CONTAINER:
        _update_container_status(db, db_item.id)

    return db_item

def delete_item(db: Session, item_id: str) -> Optional[Item]:
    db_item = get_item(db, item_id)
    if not db_item:
        return None

    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    from app.models.container import Container

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
    """Quick search items by keyword"""
    search_term = f"%{keyword}%"
    return db.query(Item).filter(
        or_(
            Item.id.ilike(search_term),
            Item.name.ilike(search_term),
            Item.manufacturer.ilike(search_term)
        )
    ).limit(limit).all()

def get_items_by_type(db: Session, item_type: ItemType) -> List[Item]:
    """Get all items by type"""
    return db.query(Item).filter(Item.item_type == item_type).order_by(Item.name).all()

def get_items_by_manufacturer(db: Session, manufacturer: str) -> List[Item]:
    """Get all items by manufacturer"""
    return db.query(Item).filter(Item.manufacturer.ilike(f"%{manufacturer}%")).order_by(Item.name).all()

def get_item_count(db: Session) -> int:
    """Get total item count"""
    return db.query(Item).count()

def get_item_count_by_type(db: Session, item_type: ItemType) -> int:
    """Get count of items by type"""
    return db.query(Item).filter(Item.item_type == item_type).count()

def get_manufacturer_count(db: Session) -> int:
    """Get count of unique manufacturers"""
    return db.query(func.count(func.distinct(Item.manufacturer))).scalar() or 0

def _to_dict_safe(pydantic_obj):
    try:
        return pydantic_obj.model_dump()  # pydantic v2
    except Exception:
        try:
            return pydantic_obj.dict()
        except Exception:
            return pydantic_obj

def create_item_response(db: Session, item: Item, base_url: str = "") -> ItemResponse:
    """Return ItemResponse with up-to-date backend-calculated stats (no client-provided totals)."""
    if item.item_type == ItemType.PARTITION:
        _update_partition_status(db, item.id)
    elif item.item_type == ItemType.LARGE_ITEM:
        _update_largeitem_status(db, item.id)
    elif item.item_type == ItemType.CONTAINER:
        _update_container_status(db, item.id)

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
            "stock_status": ps.stock_status.value if getattr(ps, "stock_status", None) else None
        }

    if getattr(item, "largeitem_stat", None):
        ls = item.largeitem_stat
        largeitem_stat = {
            "total_quantity": ls.total_quantity,
            "high_threshold": ls.high_threshold,
            "low_threshold": ls.low_threshold,
            "stock_status": ls.stock_status.value if getattr(ls, "stock_status", None) else None
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
            "stock_status": cs.stock_status.value if getattr(cs, "stock_status", None) else None
        }

    # include partition rows when item is partition type
    if item.item_type == ItemType.PARTITION:
        from app.models.partition import Partition
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
    """Return ItemStatsResponse combining create_item_response and aggregated counts."""
    item_response = create_item_response(db, item, base_url)
    base_data = _to_dict_safe(item_response)

    # counts aggregated from rows
    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    from app.models.container import Container
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item.id).scalar() or 0
    large_item_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item.id).scalar() or 0
    container_count = db.query(func.count(Container.id)).filter(Container.item_id == item.id).scalar() or 0
    total_instances = partition_count + large_item_count + container_count

    # per-type stats
    stats = {}
    if item.item_type == ItemType.PARTITION:
        p = get_partition_stats(db, item.id)
        stats = {
            "total_quantity": p["total_quantity"],
            "total_capacity": p["total_capacity"],
            "partition_count": p["partition_count"],
            "stock_status": (db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first().stock_status.value
                             if db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first() and
                                db.query(PartitionStat).filter(PartitionStat.item_id == item.id).first().stock_status else None)
        }
    elif item.item_type == ItemType.LARGE_ITEM:
        ls = db.query(LargeItemStat).filter(LargeItemStat.item_id == item.id).first()
        stats = {"stock_status": ls.stock_status.value if ls and ls.stock_status else None}
    elif item.item_type == ItemType.CONTAINER:
        c = get_container_stats(db, item.id)
        cs = db.query(ContainerStat).filter(ContainerStat.item_id == item.id).first()
        stats = {
            "total_weight": c.get("total_weight", 0.0),
            "container_count": c.get("container_count", 0),
            "stock_status": cs.stock_status.value if cs and cs.stock_status else None
        }
        if cs and cs.container_item_weight:
            stats["total_quantity"] = c.get("total_quantity", 0)

    merged = {**base_data, **stats}
    return ItemStatsResponse.model_validate(merged)

def _ensure_thresholds_valid(data: dict) -> None:
    """Defensive checks:
       - pairs high/low must be high > low when both provided
       - on create (data contains item_type) require thresholds for that type
       - partition thresholds must be percentages (0-100)
    """
    def _as_float(val, name):
        try:
            return None if val is None else float(val)
        except Exception:
            raise ValueError({"field": name, "message": f"{name} must be a number"})

    ph = _as_float(data.get("partition_high"), "partition_high")
    pl = _as_float(data.get("partition_low"), "partition_low")
    # partition highs/lows must be in percentage range 0..100
    for v, n in ((ph, "partition_high"), (pl, "partition_low")):
        if v is not None and not (0.0 <= v <= 100.0):
            raise ValueError({"field": n, "message": f"{n} must be between 0 and 100"})
    if ph is not None and pl is not None and not (ph > pl):
        raise ValueError({"field": "partition_high/low", "message": "partition_high must be greater than partition_low"})
    if data.get("item_type") == "partition":
        if ph is None or pl is None:
            raise ValueError({"field": "partition_high/low", "message": "partition_high and partition_low are required for partition items"})

    lh = data.get("large_high")
    ll = data.get("large_low")
    if lh is not None and ll is not None and not (int(lh) > int(ll)):
        raise ValueError({"field": "large_high/low", "message": "large_high must be greater than large_low"})
    if data.get("item_type") == "large_item":
        if lh is None or ll is None:
            raise ValueError({"field": "large_high/low", "message": "large_high and large_low are required for large_item items"})

    ch = data.get("container_high")
    cl = data.get("container_low")
    if ch is not None and cl is not None and not (float(ch) > float(cl)):
        raise ValueError({"field": "container_high/low", "message": "container_high must be greater than container_low"})
    if data.get("item_type") == "container":
        if ch is None or cl is None:
            raise ValueError({"field": "container_high/low", "message": "container_high and container_low are required for container items"})