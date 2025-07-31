from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import storage_slot as slot_crud
from app.schemas.storage_slot import StorageSlotCreate, StorageSlotUpdate, StorageSlotResponse

router = APIRouter(
    prefix="/storage-slots",
    tags=["storage-slots"]
)

@router.post("/", response_model=StorageSlotResponse, status_code=status.HTTP_201_CREATED)
def create_storage_slot(slot: StorageSlotCreate, db: Session = Depends(get_db)):
    """Create a new storage slot"""
    # Check if storage slot ID already exists
    if slot_crud.get_storage_slot(db, slot_id=slot.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Storage slot ID already exists"
        )
    
    return slot_crud.create_storage_slot(db=db, slot=slot)

@router.get("/", response_model=List[StorageSlotResponse])
def get_storage_slots(
    skip: int = 0, 
    limit: int = 100, 
    occupied: Optional[bool] = Query(None, description="Filter by occupation status"),
    floor: Optional[str] = Query(None, description="Filter by floor (e.g., F1, F2)"),
    db: Session = Depends(get_db)
):
    """Get all storage slots with optional filtering"""
    if floor:
        return slot_crud.get_storage_slots_by_floor(db, floor=floor)
    elif occupied is True:
        return slot_crud.get_occupied_storage_slots(db)
    elif occupied is False:
        return slot_crud.get_available_storage_slots(db)
    else:
        return slot_crud.get_storage_slots(db, skip=skip, limit=limit)

@router.get("/{slot_id}", response_model=StorageSlotResponse)
def get_storage_slot(slot_id: str, db: Session = Depends(get_db)):
    """Get storage slot by ID"""
    db_slot = slot_crud.get_storage_slot(db, slot_id=slot_id)
    if not db_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storage slot not found"
        )
    return db_slot

@router.put("/{slot_id}", response_model=StorageSlotResponse)
def update_storage_slot(slot_id: str, slot: StorageSlotUpdate, db: Session = Depends(get_db)):
    """Update storage slot"""
    db_slot = slot_crud.update_storage_slot(db, slot_id=slot_id, slot=slot)
    if not db_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storage slot not found"
        )
    return db_slot

@router.delete("/{slot_id}", response_model=StorageSlotResponse)
def delete_storage_slot(slot_id: str, db: Session = Depends(get_db)):
    """Delete storage slot"""
    db_slot = slot_crud.delete_storage_slot(db, slot_id=slot_id)
    if not db_slot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Storage slot not found"
        )
    return db_slot