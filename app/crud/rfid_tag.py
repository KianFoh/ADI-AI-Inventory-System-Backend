from sqlalchemy.orm import Session
from sqlalchemy import inspect
from app.schemas.rfid_tag import RFIDTagUpdate, RFIDTagResponse
from app.models.rfid_tag import RFIDTag
from app.models.large_item import LargeItem
from app.models.partition import Partition
from app.models.container import Container
from app.models.item import Item
from typing import List, Optional, Tuple, Dict, Any
from app.crud.general import order_by_numeric_suffix

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
) -> Tuple[List[Dict[str, Any]], int]:
    """Get RFID tags with pagination and search. Returns enriched dicts including assignment info."""
    query = db.query(RFIDTag)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(RFIDTag.id.ilike(search_term))
    
    if assigned_filter is not None:
        query = query.filter(RFIDTag.assigned == assigned_filter)
    
    total_count = query.count()
    
    skip = (page - 1) * page_size
    query = order_by_numeric_suffix(query, RFIDTag.id)
    tags = query.offset(skip).limit(page_size).all()

    results: List[Dict[str, Any]] = []
    for t in tags:
        row: Dict[str, Any] = {
            "id": t.id,
            "assigned": bool(t.assigned),
        }
        # Lookup unit and item information if assigned
        if t.assigned:
            unit = get_unit_by_rfid_tag(db, t.id)
            if unit:
                # unit dict from get_unit_by_rfid_tag includes 'id', 'item_id', 'item_name' and 'item_type'
                row["unit_id"] = unit.get("id")
                row["item_type"] = unit.get("unit_type")
                row["item_id"] = unit.get("item_id")
                row["item_name"] = unit.get("item_name")
            else:
                # assigned flag true but not found (possible data inconsistency)
                row["unit_id"] = None
                row["item_type"] = None
                row["item_id"] = None
                row["item_name"] = None
        else:
            row["unit_id"] = None
            row["item_type"] = None
            row["item_id"] = None
            row["item_name"] = None

        results.append(row)
    
    return results, total_count

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
        result["unit_type"] = "large_item"
        return result

    # check partitions
    unit = db.query(Partition).filter(Partition.rfid_tag_id == rfidtag).first()
    if unit:
        result = _model_to_dict(unit)
        item = db.query(Item).filter(Item.id == getattr(unit, "item_id", None)).first()
        result["item_name"] = item.name if item else None
        result["unit_type"] = "partition"
        result["partition_capacity"] = item.partition_stat.partition_capacity
        return result

    # check containers
    unit = db.query(Container).filter(Container.rfid_tag_id == rfidtag).first()
    if unit:
        result = _model_to_dict(unit)
        item = db.query(Item).filter(Item.id == getattr(unit, "item_id", None)).first()
        result["item_name"] = item.name if item else None
        result["unit_type"] = "container"
        result["container_weight"] = item.container_stat.container_weight
        return result

    return None