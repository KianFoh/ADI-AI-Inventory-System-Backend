from sqlalchemy.orm import Session
from app.models.rfid_tag import RFIDTag
from app.schemas.rfid_tag import RFIDTagCreate, RFIDTagUpdate
from typing import List, Optional

def get_rfid_tag(db: Session, tag_id: str) -> Optional[RFIDTag]:
    return db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()

def get_rfid_tags(db: Session, skip: int = 0, limit: int = 100) -> List[RFIDTag]:
    return db.query(RFIDTag).offset(skip).limit(limit).all()

def get_assigned_rfid_tags(db: Session) -> List[RFIDTag]:
    return db.query(RFIDTag).filter(RFIDTag.assigned == True).all()

def get_unassigned_rfid_tags(db: Session) -> List[RFIDTag]:
    return db.query(RFIDTag).filter(RFIDTag.assigned == False).all()

def create_rfid_tag(db: Session, tag: RFIDTagCreate) -> RFIDTag:
    db_tag = RFIDTag(**tag.model_dump())
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def update_rfid_tag(db: Session, tag_id: str, tag: RFIDTagUpdate) -> Optional[RFIDTag]:
    db_tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if db_tag:
        update_data = tag.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_tag, key, value)
        db.commit()
        db.refresh(db_tag)
    return db_tag

def delete_rfid_tag(db: Session, tag_id: str) -> Optional[RFIDTag]:
    db_tag = db.query(RFIDTag).filter(RFIDTag.id == tag_id).first()
    if db_tag:
        db.delete(db_tag)
        db.commit()
    return db_tag