from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, or_
from app.models.large_item import LargeItem, LargeItemStatus
from app.models.item import Item, ItemType, LargeItemStat
from app.models.storage_section import StorageSection
from app.models.rfid_tag import RFIDTag
from app.schemas.large_item import LargeItemCreate, LargeItemUpdate
from app.crud.general import (
    create_entity_with_rfid_and_storage, 
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage
)
from typing import List, Optional, Tuple
# import updater
from app.crud.item import _update_largeitem_status

def get_large_item(db: Session, large_item_id: str) -> Optional[LargeItem]:
    return db.query(LargeItem).options(
        joinedload(LargeItem.item),
        joinedload(LargeItem.storage_section),
        joinedload(LargeItem.rfid_tag)
    ).filter(LargeItem.id == large_item_id).first()

def get_large_items(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    status: Optional[LargeItemStatus] = None
) -> Tuple[List[LargeItem], int]:
    query = db.query(LargeItem).options(
        joinedload(LargeItem.item),
        joinedload(LargeItem.storage_section),
        joinedload(LargeItem.rfid_tag)
    )
    
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
    
    total_count = query.count()
    large_items = query.order_by(LargeItem.id).offset((page - 1) * page_size).limit(page_size).all()
    
    return large_items, total_count

def create_large_item(db: Session, large_item: LargeItemCreate) -> LargeItem:
    entity_data = {
        "item_id": large_item.item_id,
        "storage_section_id": large_item.storage_section_id,
        "rfid_tag_id": large_item.rfid_tag_id,
        "status": LargeItemStatus.AVAILABLE
    }
    
    created = create_entity_with_rfid_and_storage(
        db=db,
        entity_class=LargeItem,
        entity_data=entity_data,
        item_id=large_item.item_id,
        storage_section_id=large_item.storage_section_id,
        rfid_tag_id=large_item.rfid_tag_id,
        expected_item_type=ItemType.LARGE_ITEM
    )
    try:
        db.refresh(created)
        # recompute and persist totals + stock_status
        _update_largeitem_status(db, created.item_id, "Register Large Item")
        # refresh parent Item and LargeItemStat so responses reflect new totals
        item = db.query(Item).filter(Item.id == created.item_id).first()
        if item:
            db.refresh(item)
        from app.models.item import LargeItemStat as _LargeItemStat
        ls = db.query(_LargeItemStat).filter(_LargeItemStat.item_id == created.item_id).first()
        if ls:
            db.refresh(ls)
    except Exception:
        pass
    return created

def update_large_item(db: Session, large_item_id: str, large_item: LargeItemUpdate) -> Optional[LargeItem]:
    update_data = large_item.model_dump(exclude_unset=True)
    
    updated = update_entity_with_rfid_and_storage(
        db=db,
        entity_class=LargeItem,
        entity_id=large_item_id,
        update_data=update_data,
        expected_item_type=ItemType.LARGE_ITEM
    )
    if updated:
        try:
            db.refresh(updated)
            _update_largeitem_status(db, updated.item_id, "Return Large Item")
            item = db.query(Item).filter(Item.id == updated.item_id).first()
            if item:
                db.refresh(item)
        except Exception:
            pass
    return updated

def delete_large_item(db: Session, large_item_id: str) -> Optional[LargeItem]:
    current = db.query(LargeItem).filter(LargeItem.id == large_item_id).first()
    item_id = current.item_id if current else None
    deleted = delete_entity_with_rfid_and_storage(db, LargeItem, large_item_id)
    if deleted and item_id:
        try:
            _update_largeitem_status(db, item_id, "Large Item Consumed")
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                db.refresh(item)
        except Exception:
            pass
    return deleted

def get_large_items_by_item(db: Session, item_id: str) -> List[LargeItem]:
    return db.query(LargeItem).options(
        joinedload(LargeItem.item),
        joinedload(LargeItem.storage_section),
        joinedload(LargeItem.rfid_tag)
    ).filter(LargeItem.item_id == item_id).order_by(LargeItem.id).all()

def get_large_items_by_storage_section(db: Session, storage_section_id: str) -> List[LargeItem]:
    return db.query(LargeItem).options(
        joinedload(LargeItem.item),
        joinedload(LargeItem.storage_section),
        joinedload(LargeItem.rfid_tag)
    ).filter(LargeItem.storage_section_id == storage_section_id).order_by(LargeItem.id).all()

def get_large_item_count(db: Session) -> int:
    return db.query(LargeItem).count()