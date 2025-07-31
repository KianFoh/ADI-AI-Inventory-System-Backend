from sqlalchemy.orm import Session
from app.models.storage_slot import StorageSlot
from app.schemas.storage_slot import StorageSlotCreate, StorageSlotUpdate
from typing import List, Optional

def get_storage_slot(db: Session, slot_id: str) -> Optional[StorageSlot]:
    return db.query(StorageSlot).filter(StorageSlot.id == slot_id).first()

def get_storage_slots(db: Session, skip: int = 0, limit: int = 100) -> List[StorageSlot]:
    return db.query(StorageSlot).offset(skip).limit(limit).all()

def get_occupied_storage_slots(db: Session) -> List[StorageSlot]:
    return db.query(StorageSlot).filter(StorageSlot.occupied == True).all()

def get_available_storage_slots(db: Session) -> List[StorageSlot]:
    return db.query(StorageSlot).filter(StorageSlot.occupied == False).all()

def get_storage_slots_by_floor(db: Session, floor: str) -> List[StorageSlot]:
    return db.query(StorageSlot).filter(StorageSlot.id.like(f"{floor}-%")).all()

def create_storage_slot(db: Session, slot: StorageSlotCreate) -> StorageSlot:
    db_slot = StorageSlot(**slot.model_dump())
    db.add(db_slot)
    db.commit()
    db.refresh(db_slot)
    return db_slot

def update_storage_slot(db: Session, slot_id: str, slot: StorageSlotUpdate) -> Optional[StorageSlot]:
    db_slot = db.query(StorageSlot).filter(StorageSlot.id == slot_id).first()
    if db_slot:
        update_data = slot.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_slot, key, value)
        db.commit()
        db.refresh(db_slot)
    return db_slot

def delete_storage_slot(db: Session, slot_id: str) -> Optional[StorageSlot]:
    db_slot = db.query(StorageSlot).filter(StorageSlot.id == slot_id).first()
    if db_slot:
        db.delete(db_slot)
        db.commit()
    return db_slot