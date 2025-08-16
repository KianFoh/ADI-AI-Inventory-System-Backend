from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.item import Item, ItemType, MeasureMethod
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemStatsResponse
from app.utils.image import save_image_from_base64, delete_image, get_image_url
from typing import List, Optional, Tuple

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

def create_item(db: Session, item: ItemCreate) -> Item:
    """Create new item with validation and image support"""
    if get_item(db, item.id):
        raise ValueError("Item with this ID already exists")

    # Image
    image_path = None
    if item.image:
        image_path = save_image_from_base64(item.id, item.image)

    # Enforce type-specific attributes
    partition_capacity = item.partition_capacity if item.item_type == ItemType.PARTITION else None
    container_item_weight = item.container_item_weight if item.item_type == ItemType.CONTAINER else None
    container_weight = item.container_weight if item.item_type == ItemType.CONTAINER else None

    db_item = Item(
        id=item.id,
        name=item.name,
        manufacturer=item.manufacturer,
        item_type=item.item_type,
        measure_method=item.measure_method,  # already validated
        image_path=image_path,
        partition_capacity=partition_capacity,
        container_item_weight=container_item_weight,
        container_weight=container_weight
    )

    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, item_id: str, item: ItemUpdate) -> Optional[Item]:
    """Update item with type-specific validation"""
    db_item = get_item(db, item_id)
    if not db_item:
        return None

    update_data = item.model_dump(exclude_unset=True)

    # Handle ID update
    if 'id' in update_data and update_data['id'] != item_id:
        new_id = update_data.pop('id')
        if get_item(db, new_id):
            raise ValueError(f"Item with ID '{new_id}' already exists")
        db_item.id = new_id

    # Handle image
    if 'image' in update_data:
        image_value = update_data.pop('image')
        if db_item.image_path:
            delete_image(db_item.image_path)
        if image_value is None:
            db_item.image_path = None
        else:
            db_item.image_path = save_image_from_base64(db_item.id, image_value)

    # Remove measure_method (will auto-assign)
    update_data.pop('measure_method', None)


    # Prevent item_type change if there are associated partitions, large items, or containers
    if 'item_type' in update_data and update_data['item_type'] != db_item.item_type:
        from app.models.partition import Partition
        from app.models.large_item import LargeItem
        from app.models.container import Container
        has_partition = db.query(Partition).filter(Partition.item_id == item_id).first() is not None
        has_large_item = db.query(LargeItem).filter(LargeItem.item_id == item_id).first() is not None
        has_container = db.query(Container).filter(Container.item_id == item_id).first() is not None
        if has_partition or has_large_item or has_container:
            raise ValueError("Cannot change item type: item has associated partitions, large items, or containers registered under it.")

    # Assign attributes
    for key, value in update_data.items():
        setattr(db_item, key, value)

    # Enforce type-specific attributes
    if db_item.item_type == ItemType.PARTITION:
        db_item.measure_method = MeasureMethod.VISION
        db_item.container_item_weight = None
        db_item.container_weight = None
        if db_item.partition_capacity is None:
            raise ValueError("Partition must have partition_capacity")
    elif db_item.item_type == ItemType.LARGE_ITEM:
        db_item.measure_method = None
        db_item.partition_capacity = None
        db_item.container_item_weight = None
        db_item.container_weight = None
    elif db_item.item_type == ItemType.CONTAINER:
        db_item.measure_method = MeasureMethod.WEIGHT
        db_item.partition_capacity = None
        # Only set container_weight if not provided
        if db_item.container_weight is None:
            raise ValueError("Container must have container_weight defined")

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
        raise ValueError("Cannot delete item with associated partitions, large items, or containers")

    if db_item.image_path:
        delete_image(db_item.image_path)

    db.delete(db_item)
    db.commit()
    return db_item

def create_item_response(db: Session, item: Item, base_url: str = "") -> ItemResponse:
    image_url = get_image_url(item.id, base_url) if item.image_path else None
    return ItemResponse(
        id=item.id,
        name=item.name,
        manufacturer=item.manufacturer,
        item_type=item.item_type,
        measure_method=item.measure_method,
        image_url=image_url,
        partition_capacity=item.partition_capacity,
        container_item_weight=item.container_item_weight,
        container_weight=item.container_weight
    )

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