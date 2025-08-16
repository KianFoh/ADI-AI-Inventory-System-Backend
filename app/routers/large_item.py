from fastapi import APIRouter, Depends, HTTPException, status as http_status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import large_item as large_item_crud
from app.models.large_item import LargeItemStatus
from app.schemas.large_item import (
    LargeItemCreate, 
    LargeItemUpdate, 
    LargeItemResponse,
    PaginatedLargeItemsResponse
)

router = APIRouter(
    prefix="/large-items",
    tags=["large-items"]
)

@router.get("/", response_model=PaginatedLargeItemsResponse)
def get_large_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get large items with pagination and optional status/search filtering"""
    status_enum = None
    if status_filter:
        try:
            status_enum = LargeItemStatus(status_filter.lower())
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in LargeItemStatus]}"
            )
    
    large_items, total_count = large_item_crud.get_large_items(
        db, page=page, page_size=page_size, search=search, status=status_enum
    )
    
    large_item_responses = [LargeItemResponse.model_validate(li) for li in large_items]
    
    return PaginatedLargeItemsResponse.create(
        large_items=large_item_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/statuses", response_model=List[str])
def get_large_item_statuses():
    """Get available large item statuses"""
    return [s.value for s in LargeItemStatus]

@router.get("/item/{item_id}", response_model=List[LargeItemResponse])
def get_large_items_by_item(item_id: str, db: Session = Depends(get_db)):
    """Get all large items for a specific item"""
    large_items = large_item_crud.get_large_items_by_item(db, item_id)
    return [LargeItemResponse.model_validate(li) for li in large_items]

@router.get("/storage-section/{storage_section_id}", response_model=List[LargeItemResponse])
def get_large_items_by_storage_section(storage_section_id: str, db: Session = Depends(get_db)):
    """Get all large items in a storage section"""
    large_items = large_item_crud.get_large_items_by_storage_section(db, storage_section_id)
    return [LargeItemResponse.model_validate(li) for li in large_items]

@router.get("/count", response_model=int)
def get_large_item_count(db: Session = Depends(get_db)):
    """Get total large item count"""
    return large_item_crud.get_large_item_count(db)

@router.get("/{large_item_id}", response_model=LargeItemResponse)
def get_large_item(large_item_id: str, db: Session = Depends(get_db)):
    """Get large item by ID"""
    large_item = large_item_crud.get_large_item(db, large_item_id)
    if not large_item:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Large item not found"
        )
    return LargeItemResponse.model_validate(large_item)

@router.post("/", response_model=LargeItemResponse, status_code=http_status.HTTP_201_CREATED)
def create_large_item(large_item: LargeItemCreate, db: Session = Depends(get_db)):
    """Create new large item"""
    try:
        created_li = large_item_crud.create_large_item(db=db, large_item=large_item)
        return LargeItemResponse.model_validate(created_li)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{large_item_id}", response_model=LargeItemResponse)
def update_large_item(large_item_id: str, large_item: LargeItemUpdate, db: Session = Depends(get_db)):
    """Update large item (item, RFID, status, etc.)"""
    try:
        updated_li = large_item_crud.update_large_item(db, large_item_id, large_item)
        if not updated_li:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Large item not found"
            )
        return LargeItemResponse.model_validate(updated_li)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{large_item_id}", response_model=LargeItemResponse)
def delete_large_item(large_item_id: str, db: Session = Depends(get_db)):
    """Delete large item (RFID automatically unassigned)"""
    deleted_li = large_item_crud.delete_large_item(db, large_item_id)
    if not deleted_li:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Large item not found"
        )
    return LargeItemResponse.model_validate(deleted_li)