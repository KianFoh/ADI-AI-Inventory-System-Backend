from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.item import Item, ItemType, MeasureMethod
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemWithImageResponse, ItemStatsResponse
from typing import List, Optional, Tuple
import base64
import imghdr

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
    """Get items with pagination"""
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
    """Create new item with optional image"""
    if get_item(db, item.id):
        raise ValueError("Item with this ID already exists")
    
    image = None
    image_filename = None
    image_content_type = None
    
    if item.image:
        try:
            if item.image.startswith('data:'):
                image_part = item.image.split(',')[1]
            else:
                image_part = item.image
            
            image_bytes = base64.b64decode(image_part)
            
            img_type = imghdr.what(None, h=image_bytes)
            if not img_type:
                raise ValueError("Invalid image format")
            
            image = image_bytes
            image_filename = f"{item.id}_image.{img_type}"
            image_content_type = f"image/{img_type}"
            
        except Exception as e:
            raise ValueError(f"Invalid image data: {str(e)}")
    
    db_item = Item(
        id=item.id,
        name=item.name,
        manufacturer=item.manufacturer,
        item_type=item.item_type,
        measure_method=item.measure_method,
        item_weight=item.item_weight,
        partition_weight=item.partition_weight,
        unit=item.unit,
        image=image,
        image_filename=image_filename,
        image_content_type=image_content_type
    )
    
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def update_item(db: Session, item_id: str, item: ItemUpdate) -> Optional[Item]:
    """Update item"""
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    
    update_data = item.model_dump(exclude_unset=True)
    
    if 'image' in update_data:
        image_value = update_data.pop('image')
        
        if image_value is None:
            db_item.image = None
            db_item.image_filename = None
            db_item.image_content_type = None
        else:
            try:
                if image_value.startswith('data:'):
                    image_part = image_value.split(',')[1]
                else:
                    image_part = image_value
                
                image_bytes = base64.b64decode(image_part)
                img_type = imghdr.what(None, h=image_bytes)
                if not img_type:
                    raise ValueError("Invalid image format")
                
                db_item.image = image_bytes
                db_item.image_filename = f"{item_id}_image.{img_type}"
                db_item.image_content_type = f"image/{img_type}"
                
            except Exception as e:
                raise ValueError(f"Invalid image data: {str(e)}")
    
    for key, value in update_data.items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    return db_item

def delete_item(db: Session, item_id: str) -> Optional[Item]:
    """Delete item"""
    db_item = get_item(db, item_id)
    if not db_item:
        return None
    
    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar()
    large_item_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar()
    
    if partition_count > 0 or large_item_count > 0:
        raise ValueError("Cannot delete item that has associated partitions or large items")
    
    db.delete(db_item)
    db.commit()
    return db_item

def create_item_response(db: Session, item: Item) -> ItemResponse:
    """Create ItemResponse from Item model"""
    return ItemResponse(
        id=item.id,
        name=item.name,
        manufacturer=item.manufacturer,
        item_type=item.item_type,
        measure_method=item.measure_method,
        item_weight=item.item_weight,
        partition_weight=item.partition_weight,
        unit=item.unit,
        image_filename=item.image_filename,
        image_content_type=item.image_content_type
    )

def get_item_image(db: Session, item_id: str) -> Optional[ItemWithImageResponse]:
    """Get item with image data"""
    item = get_item(db, item_id)
    if not item:
        return None
    
    item_response = create_item_response(db, item)
    
    image = None
    if item.image:
        image = base64.b64encode(item.image).decode('utf-8')
        if item.image_content_type:
            image = f"data:{item.image_content_type};base64,{image}"
    
    return ItemWithImageResponse(
        **item_response.model_dump(),
        image=image
    )

def get_item_with_stats(db: Session, item_id: str) -> Optional[ItemStatsResponse]:
    """Get item with detailed statistics"""
    item = get_item(db, item_id)
    if not item:
        return None
    
    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    
    partition_count = db.query(func.count(Partition.id)).filter(Partition.item_id == item_id).scalar() or 0
    large_item_count = db.query(func.count(LargeItem.id)).filter(LargeItem.item_id == item_id).scalar() or 0
    total_instances = partition_count + large_item_count
    
    item_response = create_item_response(db, item)
    
    return ItemStatsResponse(
        **item_response.model_dump(),
        partition_count=partition_count,
        large_item_count=large_item_count,
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