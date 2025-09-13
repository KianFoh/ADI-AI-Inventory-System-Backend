from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.item import Item, ItemType, MeasureMethod
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemStatsResponse
from app.utils.image import save_image_from_base64, delete_image, get_image_url
from typing import List, Optional, Tuple, Dict, Union

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

def create_item(db: Session, item: Union[ItemCreate, dict]) -> Item:
    """Create new item with validation and image support. Accepts ItemCreate or dict."""
    data = _normalize_input_to_dict(item)

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
        partition_capacity=data.get("partition_capacity"),
        container_item_weight=data.get("container_item_weight"),
        container_weight=data.get("container_weight"),
        # new fields
        process=data.get("process"),
        tooling_used=data.get("tooling_used"),
        vendor_pn=data.get("vendor_pn"),
        sap_pn=data.get("sap_pn"),
        package_used=data.get("package_used"),
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, item_id: str, item: Union[ItemUpdate, dict]) -> Optional[Item]:
    """Update item with type-specific validation. Accepts ItemUpdate or dict."""
    db_item = get_item(db, item_id)
    if not db_item:
        return None

    update_data = _normalize_input_to_dict(item)
    # combine enum normalization if provided as strings
    if "item_type" in update_data and isinstance(update_data["item_type"], str):
        update_data["item_type"] = ItemType(update_data["item_type"])
    if "measure_method" in update_data and isinstance(update_data["measure_method"], str):
        update_data["measure_method"] = MeasureMethod(update_data["measure_method"])

    # Handle image field
    if 'image' in update_data:
        image_value = update_data.pop('image')
        if db_item.image_path:
            delete_image(db_item.image_path)
        if image_value is None:
            db_item.image_path = None
        else:
            db_item.image_path = save_image_from_base64(db_item.id, image_value)

    # assign other fields (includes new metadata fields)
    for key, value in update_data.items():
        setattr(db_item, key, value)

    # Enforce type-specific attributes (existing logic)
    if db_item.item_type == ItemType.PARTITION:
        db_item.measure_method = MeasureMethod.VISION
        db_item.container_item_weight = None
        db_item.container_weight = None
        if db_item.partition_capacity is None:
            raise ValueError({"field": "partition_capacity", "message": "Partition must have partition_capacity"})
    elif db_item.item_type == ItemType.LARGE_ITEM:
        db_item.measure_method = None
        db_item.partition_capacity = None
        db_item.container_item_weight = None
        db_item.container_weight = None
    elif db_item.item_type == ItemType.CONTAINER:
        db_item.measure_method = MeasureMethod.WEIGHT
        db_item.partition_capacity = None
        if db_item.container_weight is None:
            raise ValueError({"field": "container_weight", "message": "Container must have container_weight defined"})

    db.commit()
    db.refresh(db_item)
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

def create_item_response(db: Session, item: Item, base_url: str = "") -> ItemResponse:
    image_url = get_image_url(item.id, base_url) if item.image_path else None
    return ItemResponse.model_validate({
        "id": item.id,
        "name": item.name,
        "manufacturer": item.manufacturer,
        "item_type": item.item_type,
        "measure_method": item.measure_method,
        "image_url": image_url,
        "container_item_weight": item.container_item_weight,
        "container_weight": item.container_weight,
        "partition_capacity": item.partition_capacity,
        # new fields
        "process": item.process,
        "tooling_used": item.tooling_used,
        "vendor_pn": item.vendor_pn,
        "sap_pn": item.sap_pn,
        "package_used": item.package_used,
    })

def get_item_with_stats(db: Session, item_id: str, base_url: str = "") -> Optional[ItemStatsResponse]:
    item = get_item(db, item_id)
    if not item:
        return None

    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    from app.models.container import Container

    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    large_item_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    container_count = db.query(func.count(Container.id)).filter(Container.item_id == item_id).scalar() or 0
    total_instances = partition_count + large_item_count + container_count

    item_response = create_item_response(db, item, base_url)

    return ItemStatsResponse(
        **item_response.model_dump(),
        partition_count=partition_count,
        large_item_count=large_item_count,
        container_count=container_count,
        total_instances=total_instances
    )

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

def get_partition_stats(db: Session, item_id: str) -> Dict[str, int]:
    from app.models.partition import Partition
    # number of partitions and total quantity
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    total_quantity = db.query(func.coalesce(func.sum(Partition.quantity), 0)).filter(Partition.item_id == item_id).scalar() or 0

    # get configured capacity per partition from item
    item = db.query(Item).filter(Item.id == item_id).first()
    per_capacity = int(item.partition_capacity) if item and item.partition_capacity else 0
    total_capacity = int(partition_count) * per_capacity

    return {
        "partition_count": int(partition_count),
        "total_quantity": int(total_quantity),
        "total_capacity": int(total_capacity),
    }

def get_large_item_stats(db: Session, item_id: str) -> Dict[str, int]:
    from app.models.large_item import LargeItem
    large_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    return {
        "large_item_count": int(large_count),
        "total_quantity": int(large_count)
    }

def get_container_stats(db: Session, item_id: str) -> Dict[str, object]:
    from app.models.container import Container
    container_count = db.query(func.count(Container.id)).filter(Container.item_id == item_id).scalar() or 0
    total_weight = db.query(func.sum(Container.items_weight)).filter(Container.item_id == item_id).scalar()
    total_quantity = db.query(func.coalesce(func.sum(Container.quantity), 0)).filter(Container.item_id == item_id).scalar() or 0

    return {
        "container_count": int(container_count),
        "total_weight": float(total_weight) if total_weight is not None else 0.0,
        "total_quantity": int(total_quantity)
    }

def build_item_with_stats(db: Session, item: Item, base_url: str) -> ItemStatsResponse:
    base_resp = create_item_response(db, item, base_url)
    base_data = _to_dict_safe(base_resp)

    stats = {}
    if item.item_type == ItemType.PARTITION:
        p = get_partition_stats(db, item.id)
        stats = {
            "total_quantity": p.get("total_quantity", 0),
            "total_capacity": p.get("total_capacity", 0),
            "partition_count": p.get("partition_count", 0),
        }
    elif item.item_type == ItemType.LARGE_ITEM:
        l = get_large_item_stats(db, item.id)
        stats = {
            "total_quantity": l.get("total_quantity", 0)
        }
    elif item.item_type == ItemType.CONTAINER:
        c = get_container_stats(db, item.id)
        # always include total_weight and the container count
        stats = {
            "total_weight": c.get("total_weight", 0.0),
            "container_count": c.get("container_count", 0)
        }
        # include total_quantity only if item has container_item_weight configured
        if getattr(item, "container_item_weight", None):
            stats["total_quantity"] = c.get("total_quantity", 0)

    merged = {**base_data, **stats}
    # validate/serialize to ItemStatsResponse so FastAPI returns only defined fields
    return ItemStatsResponse.model_validate(merged)