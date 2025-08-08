from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.large_item import LargeItem, LargeItemStatus
from app.models.rfid_tag import RFIDTag
from app.models.item import Item
from app.schemas.large_item import LargeItemCreate, LargeItemUpdate
from typing import List, Optional, Tuple

def get_large_item(db: Session, large_item_id: str) -> Optional[LargeItem]:
    return db.query(LargeItem).filter(LargeItem.id == large_item_id).first()

def get_large_items(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    status: Optional[LargeItemStatus] = None
) -> Tuple[List[LargeItem], int]:
    """Get large items with pagination"""
    query = db.query(LargeItem)
    
    if search:
        search_term = f"%{search}%"
        query = query.join(LargeItem.item).filter(
            or_(
                LargeItem.id.ilike(search_term),
                Item.name.ilike(search_term)
            )
        )
    
    if status:
        query = query.filter(LargeItem.status == status)
    
    query = query.order_by(LargeItem.id)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    large_items = query.offset(skip).limit(page_size).all()
    
    return large_items, total_count

def create_large_item(db: Session, large_item: LargeItemCreate) -> LargeItem:
    """Create new large item - RFID tag is REQUIRED"""
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == large_item.rfid_tag_id).first()
    if not rfid_tag:
        raise ValueError("RFID tag not found")
    
    if rfid_tag.assigned:
        raise ValueError("RFID tag is already assigned")
    
    db_large_item = LargeItem(
        item_id=large_item.item_id,
        storage_section_id=large_item.storage_section_id,
        rfid_tag_id=large_item.rfid_tag_id,
        status=LargeItemStatus.AVAILABLE
    )
    
    db.add(db_large_item)
    rfid_tag.assigned = True
    db.commit()
    db.refresh(db_large_item)
    
    return db_large_item

def update_large_item(db: Session, large_item_id: str, large_item: LargeItemUpdate) -> Optional[LargeItem]:
    """Update large item - RFID tag is permanent"""
    db_large_item = db.query(LargeItem).filter(LargeItem.id == large_item_id).first()
    if not db_large_item:
        return None
    
    update_data = large_item.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_large_item, key, value)
    
    db.commit()
    db.refresh(db_large_item)
    return db_large_item

def delete_large_item(db: Session, large_item_id: str) -> Optional[LargeItem]:
    """Delete large item and release RFID tag"""
    db_large_item = db.query(LargeItem).filter(LargeItem.id == large_item_id).first()
    if not db_large_item:
        return None
    
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == db_large_item.rfid_tag_id).first()
    if rfid_tag:
        rfid_tag.assigned = False
    
    db.delete(db_large_item)
    db.commit()
    
    return db_large_item

def update_large_item_status(db: Session, large_item_id: str, status: LargeItemStatus) -> Optional[LargeItem]:
    """Update large item status"""
    db_large_item = db.query(LargeItem).filter(LargeItem.id == large_item_id).first()
    if not db_large_item:
        return None
    
    db_large_item.status = status
    db.commit()
    db.refresh(db_large_item)
    return db_large_item

def get_large_items_by_status(db: Session, status: LargeItemStatus) -> List[LargeItem]:
    """Get all large items with specific status"""
    return db.query(LargeItem).filter(LargeItem.status == status).order_by(LargeItem.id).all()

def get_available_large_items(db: Session) -> List[LargeItem]:
    """Get all available large items"""
    return db.query(LargeItem).filter(LargeItem.status == LargeItemStatus.AVAILABLE).order_by(LargeItem.id).all()

def get_large_items_by_storage_section(db: Session, storage_section_id: str) -> List[LargeItem]:
    """Get all large items in a specific storage section"""
    return db.query(LargeItem).filter(LargeItem.storage_section_id == storage_section_id).order_by(LargeItem.id).all()

def get_large_items_by_item(db: Session, item_id: str) -> List[LargeItem]:
    """Get all large items for a specific item"""
    return db.query(LargeItem).filter(LargeItem.item_id == item_id).order_by(LargeItem.id).all()

def search_large_items_by_name(db: Session, name: str, limit: int = 20) -> List[LargeItem]:
    """Search large items by item name"""
    search_term = f"%{name}%"
    return db.query(LargeItem).join(LargeItem.item).filter(
        Item.name.ilike(search_term)
    ).order_by(Item.name).limit(limit).all()

def get_large_item_count(db: Session) -> int:
    """Get total large item count"""
    return db.query(LargeItem).count()

def get_large_item_count_by_status(db: Session, status: LargeItemStatus) -> int:
    """Get count of large items by status"""
    return db.query(LargeItem).filter(LargeItem.status == status).count()