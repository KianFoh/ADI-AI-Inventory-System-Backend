from fastapi import APIRouter, Depends, HTTPException, status, Query
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
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search by large item ID or item name"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    status_enum = None
    if status:
        try:
            status_enum = LargeItemStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in LargeItemStatus]}"
            )
    
    large_items, total_count = large_item_crud.get_large_items(
        db, 
        page=page, 
        page_size=page_size, 
        search=search,
        status=status_enum
    )
    
    large_item_responses = [LargeItemResponse.model_validate(large_item) for large_item in large_items]
    
    return PaginatedLargeItemsResponse.create(
        large_items=large_item_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/search", response_model=List[LargeItemResponse])
def search_large_items(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    large_items = large_item_crud.search_large_items_by_name(db, name=q, limit=limit)
    return [LargeItemResponse.model_validate(large_item) for large_item in large_items]

@router.get("/statuses", response_model=List[str])
def get_large_item_statuses():
    return [status.value for status in LargeItemStatus]

@router.get("/available", response_model=List[LargeItemResponse])
def get_available_large_items(db: Session = Depends(get_db)):
    large_items = large_item_crud.get_available_large_items(db)
    return [LargeItemResponse.model_validate(large_item) for large_item in large_items]

@router.get("/status/{status}", response_model=List[LargeItemResponse])
def get_large_items_by_status(status: str, db: Session = Depends(get_db)):
    try:
        status_enum = LargeItemStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in LargeItemStatus]}"
        )
    
    large_items = large_item_crud.get_large_items_by_status(db, status_enum)
    return [LargeItemResponse.model_validate(large_item) for large_item in large_items]

@router.get("/item/{item_id}", response_model=List[LargeItemResponse])
def get_large_items_by_item(item_id: str, db: Session = Depends(get_db)):
    large_items = large_item_crud.get_large_items_by_item(db, item_id)
    return [LargeItemResponse.model_validate(large_item) for large_item in large_items]

@router.get("/storage-section/{storage_section_id}", response_model=List[LargeItemResponse])
def get_large_items_by_storage_section(storage_section_id: str, db: Session = Depends(get_db)):
    large_items = large_item_crud.get_large_items_by_storage_section(db, storage_section_id)
    return [LargeItemResponse.model_validate(large_item) for large_item in large_items]

@router.get("/{large_item_id}", response_model=LargeItemResponse)
def get_large_item(large_item_id: str, db: Session = Depends(get_db)):
    large_item = large_item_crud.get_large_item(db, large_item_id=large_item_id)
    if not large_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Large item not found"
        )
    return LargeItemResponse.model_validate(large_item)

@router.post("/", response_model=LargeItemResponse, status_code=status.HTTP_201_CREATED)
def create_large_item(large_item: LargeItemCreate, db: Session = Depends(get_db)):
    try:
        created_large_item = large_item_crud.create_large_item(db=db, large_item=large_item)
        return LargeItemResponse.model_validate(created_large_item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{large_item_id}", response_model=LargeItemResponse)
def update_large_item(large_item_id: str, large_item: LargeItemUpdate, db: Session = Depends(get_db)):
    try:
        updated_large_item = large_item_crud.update_large_item(db, large_item_id=large_item_id, large_item=large_item)
        if not updated_large_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Large item not found"
            )
        return LargeItemResponse.model_validate(updated_large_item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.patch("/{large_item_id}/status", response_model=LargeItemResponse)
def update_large_item_status(
    large_item_id: str, 
    new_status: str = Query(..., description="New status for the large item"),
    db: Session = Depends(get_db)
):
    try:
        status_enum = LargeItemStatus(new_status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in LargeItemStatus]}"
        )
    
    updated_large_item = large_item_crud.update_large_item_status(db, large_item_id, status_enum)
    if not updated_large_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Large item not found"
        )
    return LargeItemResponse.model_validate(updated_large_item)

@router.delete("/{large_item_id}", response_model=LargeItemResponse)
def delete_large_item(large_item_id: str, db: Session = Depends(get_db)):
    deleted_large_item = large_item_crud.delete_large_item(db, large_item_id=large_item_id)
    if not deleted_large_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Large item not found"
        )
    return LargeItemResponse.model_validate(deleted_large_item)

@router.get("/count/total", response_model=int)
def get_large_item_count(db: Session = Depends(get_db)):
    return large_item_crud.get_large_item_count(db)

@router.get("/count/status/{status}", response_model=int)
def get_large_item_count_by_status(status: str, db: Session = Depends(get_db)):
    try:
        status_enum = LargeItemStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in LargeItemStatus]}"
        )
    
    return large_item_crud.get_large_item_count_by_status(db, status_enum)