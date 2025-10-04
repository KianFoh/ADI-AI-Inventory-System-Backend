from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text, inspect
from app.schemas.rfid_tag import RFIDTagCreate, RFIDTagUpdate, RFIDTagResponse
from app.models.rfid_tag import RFIDTag
from app.models.large_item import LargeItem
from app.models.partition import Partition
from app.models.container import Container
from app.models.item import Item
from typing import List, Optional, Tuple

def get_rfid_tag(db: Session, tag_id: str) -> Optional[RFIDTagResponse]:
    tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if tag:
        return RFIDTagResponse.model_validate(tag)
    return None

def get_rfid_tags(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    assigned_filter: Optional[bool] = None
) -> Tuple[List[RFIDTag], int]:
    """Get RFID tags with pagination and search"""
    query = db.query(RFIDTag)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(RFIDTag.id.ilike(search_term))
    
    if assigned_filter is not None:
        query = query.filter(RFIDTag.assigned == assigned_filter)
    
    total_count = query.count()
    
    skip = (page - 1) * page_size
    tags = query.order_by(RFIDTag.id).offset(skip).limit(page_size).all()
    
    return tags, total_count

def create_rfid_tag(db: Session) -> RFIDTagResponse:
    db_tag = RFIDTag(assigned=False)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return RFIDTagResponse.model_validate(db_tag)

def update_rfid_tag(db: Session, tag_id: str, tag: RFIDTagUpdate) -> Optional[RFIDTagResponse]:
    db_tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if db_tag:
        db_tag.assigned = tag.assigned
        db.commit()
        db.refresh(db_tag)
        return RFIDTagResponse.model_validate(db_tag)
    return None

def delete_rfid_tag(db: Session, tag_id: str) -> Optional[RFIDTagResponse]:
    db_tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if db_tag:
        if db_tag.assigned:
            raise ValueError({"field": "tag_id", "message": f"Cannot delete assigned RFID tag {tag_id}. Unassign it first."})
        
        result = RFIDTagResponse.model_validate(db_tag)
        db.delete(db_tag)
        db.commit()
        return result
    return None

def get_unassigned_rfid_tags(db: Session) -> List[RFIDTag]:
    return db.query(RFIDTag).filter(RFIDTag.assigned == False).order_by(RFIDTag.id).all()

def get_assigned_rfid_tags(db: Session) -> List[RFIDTag]:
    return db.query(RFIDTag).filter(RFIDTag.assigned == True).order_by(RFIDTag.id).all()

def search_rfid_tags_by_keyword(db: Session, keyword: str, limit: int = 20) -> List[RFIDTag]:
    """Quick search for autocomplete/dropdown"""
    search_term = f"%{keyword}%"
    return db.query(RFIDTag).filter(
        RFIDTag.id.ilike(search_term)
    ).order_by(RFIDTag.id).limit(limit).all()

def get_available_rfid_tags_for_assignment(db: Session, limit: int = 50) -> List[RFIDTag]:
    """Get unassigned RFID tags available for assignment"""
    return db.query(RFIDTag).filter(
        RFIDTag.assigned == False
    ).order_by(RFIDTag.id).limit(limit).all()

def check_rfid_availability(db: Session, tag_id: str) -> bool:
    tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    return tag is not None and not tag.assigned

def assign_rfid_tag(db: Session, tag_id: str) -> Optional[RFIDTagResponse]:
    db_tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if db_tag and not db_tag.assigned:
        db_tag.assigned = True
        db.commit()
        db.refresh(db_tag)
        return RFIDTagResponse.model_validate(db_tag)
    return None

def unassign_rfid_tag(db: Session, tag_id: str) -> Optional[RFIDTagResponse]:
    db_tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if db_tag and db_tag.assigned:
        db_tag.assigned = False
        db.commit()
        db.refresh(db_tag)
        return RFIDTagResponse.model_validate(db_tag)
    return None

def get_rfid_tag_count(db: Session) -> int:
    """Get total RFID tag count"""
    return db.query(RFIDTag).count()

def get_assigned_tag_count(db: Session) -> int:
    """Get count of assigned tags"""
    return db.query(RFIDTag).filter(RFIDTag.assigned == True).count()

def get_unassigned_tag_count(db: Session) -> int:
    """Get count of unassigned tags"""
    return db.query(RFIDTag).filter(RFIDTag.assigned == False).count()

def _model_to_dict(instance):
    mapper = inspect(instance.__class__)
    return {c.key: getattr(instance, c.key) for c in mapper.column_attrs}

def get_unit_by_rfid_tag(db: Session, rfidtag: str):
    """Return first matching record from large_items / partitions / containers for the given rfidtag
    as a plain dict including the linked item name (item_name), or None.
    Uses SQLAlchemy ORM instead of raw SQL.
    """
    # import models here to avoid circular import at module import time


    # check large items
    unit = db.query(LargeItem).filter(LargeItem.rfid_tag_id == rfidtag).first()
    if unit:
        result = _model_to_dict(unit)
        item = db.query(Item).filter(Item.id == getattr(unit, "item_id", None)).first()
        result["item_name"] = item.name if item else None
        result["unit_table"] = "large_items"
        return result

    # check partitions
    unit = db.query(Partition).filter(Partition.rfid_tag_id == rfidtag).first()
    if unit:
        result = _model_to_dict(unit)
        item = db.query(Item).filter(Item.id == getattr(unit, "item_id", None)).first()
        result["item_name"] = item.name if item else None
        result["unit_table"] = "partitions"
        return result

    # check containers
    unit = db.query(Container).filter(Container.rfid_tag_id == rfidtag).first()
    if unit:
        result = _model_to_dict(unit)
        item = db.query(Item).filter(Item.id == getattr(unit, "item_id", None)).first()
        result["item_name"] = item.name if item else None
        result["unit_table"] = "containers"
        return result

    return None