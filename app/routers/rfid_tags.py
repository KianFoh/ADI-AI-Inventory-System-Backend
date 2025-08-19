from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import rfid_tag as rfid_crud
from app.schemas.rfid_tag import (
    RFIDTagCreate, 
    RFIDTagUpdate, 
    RFIDTagResponse,
    PaginatedRFIDTagsResponse
)

router = APIRouter(
    prefix="/rfid-tags",
    tags=["rfid-tags"]
)

@router.get("/", response_model=PaginatedRFIDTagsResponse)
def get_rfid_tags(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search by tag ID"),
    assigned: Optional[bool] = Query(None, description="Filter by assignment status (true/false)"),
    db: Session = Depends(get_db)
):
    """Get RFID tags with pagination and search"""
    tags, total_count = rfid_crud.get_rfid_tags(
        db, 
        page=page, 
        page_size=page_size, 
        search=search,
        assigned_filter=assigned
    )
    
    tag_responses = [RFIDTagResponse.model_validate(tag) for tag in tags]
    
    return PaginatedRFIDTagsResponse.create(
        tags=tag_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/search", response_model=List[RFIDTagResponse])
def search_rfid_tags(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Quick search RFID tags for autocomplete/dropdown"""
    tags = rfid_crud.search_rfid_tags_by_keyword(db, keyword=q, limit=limit)
    return [RFIDTagResponse.model_validate(tag) for tag in tags]

@router.get("/assigned", response_model=List[RFIDTagResponse])
def get_assigned_rfid_tags(db: Session = Depends(get_db)):
    """Get all assigned RFID tags"""
    tags = rfid_crud.get_assigned_rfid_tags(db)
    return [RFIDTagResponse.model_validate(tag) for tag in tags]

@router.get("/unassigned", response_model=List[RFIDTagResponse])
def get_unassigned_rfid_tags(db: Session = Depends(get_db)):
    """Get all unassigned RFID tags"""
    tags = rfid_crud.get_unassigned_rfid_tags(db)
    return [RFIDTagResponse.model_validate(tag) for tag in tags]

@router.get("/{tag_id}", response_model=RFIDTagResponse)
def get_rfid_tag(tag_id: str, db: Session = Depends(get_db)):
    """Get RFID tag by ID"""
    tag = rfid_crud.get_rfid_tag(db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"field": "tag_id", "message": "RFID tag not found"}
        )
    return tag

@router.post("/", response_model=RFIDTagResponse, status_code=status.HTTP_201_CREATED)
def create_rfid_tag(tag: RFIDTagCreate, db: Session = Depends(get_db)):
    """Create new RFID tag"""
    # Check if tag already exists
    existing_tag = rfid_crud.get_rfid_tag(db, tag_id=tag.id)
    if existing_tag:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "tag_id", "message": "RFID tag with this ID already exists"}
        )
    return rfid_crud.create_rfid_tag(db=db, tag=tag)

@router.put("/{tag_id}", response_model=RFIDTagResponse)
def update_rfid_tag(tag_id: str, tag: RFIDTagUpdate, db: Session = Depends(get_db)):
    """Update RFID tag"""
    updated_tag = rfid_crud.update_rfid_tag(db, tag_id=tag_id, tag=tag)
    if not updated_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"field": "tag_id", "message": "RFID tag not found"}
        )
    return updated_tag

@router.delete("/{tag_id}", response_model=RFIDTagResponse)
def delete_rfid_tag(tag_id: str, db: Session = Depends(get_db)):
    """Delete RFID tag"""
    try:
        deleted_tag = rfid_crud.delete_rfid_tag(db, tag_id=tag_id)
        if not deleted_tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"field": "tag_id", "message": "RFID tag not found"}
            )
        return deleted_tag
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "tag_id", "message": str(e)}
        )

@router.post("/{tag_id}/assign", response_model=RFIDTagResponse)
def assign_rfid_tag(tag_id: str, db: Session = Depends(get_db)):
    """Assign RFID tag"""
    tag = rfid_crud.assign_rfid_tag(db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"field": "tag_id", "message": "RFID tag not found or already assigned"}
        )
    return tag

@router.post("/{tag_id}/unassign", response_model=RFIDTagResponse)
def unassign_rfid_tag(tag_id: str, db: Session = Depends(get_db)):
    """Unassign RFID tag"""
    tag = rfid_crud.unassign_rfid_tag(db, tag_id=tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"field": "tag_id", "message": "RFID tag not found or already unassigned"}
        )
    return tag

@router.get("/{tag_id}/check-availability", response_model=dict)
def check_tag_availability(tag_id: str, db: Session = Depends(get_db)):
    """Check if RFID tag is available for assignment"""
    is_available = rfid_crud.check_rfid_availability(db, tag_id)
    return {
        "tag_id": tag_id,
        "is_available": is_available,
        "message": "Tag is available for assignment" if is_available else "Tag is not available or already assigned"
    }

@router.get("/count/total", response_model=int)
def get_rfid_tag_count(db: Session = Depends(get_db)):
    """Get total RFID tag count"""
    return rfid_crud.get_rfid_tag_count(db)

@router.get("/count/assigned", response_model=int)
def get_assigned_tag_count(db: Session = Depends(get_db)):
    """Get assigned tag count"""
    return rfid_crud.get_assigned_tag_count(db)

@router.get("/count/unassigned", response_model=int)
def get_unassigned_tag_count(db: Session = Depends(get_db)):
    """Get unassigned tag count"""
    return rfid_crud.get_unassigned_tag_count(db)