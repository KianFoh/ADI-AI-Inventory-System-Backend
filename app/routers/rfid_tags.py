from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import rfid_tag as rfid_crud
from app.schemas.rfid_tag import RFIDTagCreate, RFIDTagUpdate, RFIDTagResponse

router = APIRouter(
    prefix="/rfid-tags",
    tags=["rfid-tags"]
)

@router.post("/", response_model=RFIDTagResponse, status_code=status.HTTP_201_CREATED)
def create_rfid_tag(tag: RFIDTagCreate, db: Session = Depends(get_db)):
    """Create a new RFID tag"""
    # Check if RFID tag ID already exists
    if rfid_crud.get_rfid_tag(db, tag_id=tag.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFID tag ID already exists"
        )
    
    return rfid_crud.create_rfid_tag(db=db, tag=tag)

@router.get("/", response_model=List[RFIDTagResponse])
def get_rfid_tags(
    skip: int = 0, 
    limit: int = 100, 
    assigned: Optional[bool] = Query(None, description="Filter by assignment status"),
    db: Session = Depends(get_db)
):
    """Get all RFID tags with optional filtering"""
    if assigned is True:
        return rfid_crud.get_assigned_rfid_tags(db)
    elif assigned is False:
        return rfid_crud.get_unassigned_rfid_tags(db)
    else:
        return rfid_crud.get_rfid_tags(db, skip=skip, limit=limit)

@router.get("/{tag_id}", response_model=RFIDTagResponse)
def get_rfid_tag(tag_id: str, db: Session = Depends(get_db)):
    """Get RFID tag by ID"""
    db_tag = rfid_crud.get_rfid_tag(db, tag_id=tag_id)
    if not db_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFID tag not found"
        )
    return db_tag

@router.put("/{tag_id}", response_model=RFIDTagResponse)
def update_rfid_tag(tag_id: str, tag: RFIDTagUpdate, db: Session = Depends(get_db)):
    """Update RFID tag"""
    db_tag = rfid_crud.update_rfid_tag(db, tag_id=tag_id, tag=tag)
    if not db_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFID tag not found"
        )
    return db_tag

@router.delete("/{tag_id}", response_model=RFIDTagResponse)
def delete_rfid_tag(tag_id: str, db: Session = Depends(get_db)):
    """Delete RFID tag"""
    db_tag = rfid_crud.delete_rfid_tag(db, tag_id=tag_id)
    if not db_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RFID tag not found"
        )
    return db_tag