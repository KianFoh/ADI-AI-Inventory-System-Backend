from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_, desc
from app.models.large_item import LargeItem, LargeItemStatus
from app.models.item import Item, ItemType
from app.models.storage_section import StorageSection
from app.models.rfid_tag import RFIDTag
from app.schemas.large_item import LargeItemCreate, LargeItemUpdate, LargeItemResponse
from app.crud.general import (
    create_entity_with_rfid_and_storage, 
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage  # ✅ IMPORT GENERIC UPDATE
)
from typing import List, Optional, Tuple

def get_large_item(db: Session, large_item_id: str) -> Optional[LargeItem]:
    """Get large item by ID"""
    return db.query(LargeItem).filter(LargeItem.id == large_item_id).first()

def get_large_items(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    status: Optional[LargeItemStatus] = None
) -> Tuple[List[LargeItem], int]:
    """Get large items with pagination and filtering"""
    query = db.query(LargeItem)
    
    if search:
        search_term = f"%{search}%"
        query = query.join(Item).join(StorageSection).filter(
            or_(
                LargeItem.id.ilike(search_term),
                Item.name.ilike(search_term),
                StorageSection.id.ilike(search_term)
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
    """Create new large item using generic function"""
    
    entity_data = {
        'item_id': large_item.item_id,
        'storage_section_id': large_item.storage_section_id,
        'rfid_tag_id': large_item.rfid_tag_id,
        'status': LargeItemStatus.AVAILABLE
    }
    
    return create_entity_with_rfid_and_storage(
        db=db,
        entity_class=LargeItem,
        entity_data=entity_data,
        item_id=large_item.item_id,
        storage_section_id=large_item.storage_section_id,
        rfid_tag_id=large_item.rfid_tag_id,
        expected_item_type=ItemType.LARGE_ITEM
    )

def update_large_item(db: Session, large_item_id: str, large_item: LargeItemUpdate) -> Optional[LargeItem]:
    """Update large item using generic function"""
    update_data = large_item.model_dump(exclude_unset=True)
    
    return update_entity_with_rfid_and_storage(
        db=db,
        entity_class=LargeItem,
        entity_id=large_item_id,
        update_data=update_data,
        expected_item_type=ItemType.LARGE_ITEM
    )

def delete_large_item(db: Session, large_item_id: str) -> Optional[LargeItem]:
    """Delete large item using generic function"""
    return delete_entity_with_rfid_and_storage(db, LargeItem, large_item_id)

def get_large_items_by_item(db: Session, item_id: str) -> List[LargeItem]:
    """Get large items by item ID"""
    return db.query(LargeItem).filter(LargeItem.item_id == item_id).order_by(LargeItem.id).all()

def get_large_items_by_storage_section(db: Session, storage_section_id: str) -> List[LargeItem]:
    """Get large items by storage section ID"""
    return db.query(LargeItem).filter(LargeItem.storage_section_id == storage_section_id).order_by(LargeItem.id).all()

def get_large_item_count(db: Session) -> int:
    """Get total large item count"""
    return db.query(LargeItem).count()