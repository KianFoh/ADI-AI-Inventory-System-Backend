from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import item as item_crud
from app.models.item import ItemType, MeasureMethod
from app.schemas.item import (
    ItemCreate, 
    ItemUpdate, 
    ItemResponse,
    ItemWithImageResponse,
    ItemStatsResponse,
    PaginatedItemsResponse
)

router = APIRouter(
    prefix="/items",
    tags=["items"]
)

@router.get("/", response_model=PaginatedItemsResponse)
def get_items(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search by item ID, name, or manufacturer"),
    item_type: Optional[str] = Query(None, description="Filter by item type"),
    manufacturer: Optional[str] = Query(None, description="Filter by manufacturer"),
    db: Session = Depends(get_db)
):
    """Get items with pagination and search"""
    # Convert string item_type to enum
    item_type_enum = None
    if item_type:
        try:
            item_type_enum = ItemType(item_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid item type. Must be one of: {[t.value for t in ItemType]}"
            )
    
    items, total_count = item_crud.get_items(
        db, page=page, page_size=page_size, search=search, 
        item_type=item_type_enum, manufacturer=manufacturer
    )
    
    item_responses = [item_crud.create_item_response(db, item) for item in items]
    
    return PaginatedItemsResponse.create(
        items=item_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/search", response_model=List[ItemResponse])
def search_items(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Quick search items for autocomplete/dropdown"""
    items = item_crud.search_items_by_keyword(db, keyword=q, limit=limit)
    return [item_crud.create_item_response(db, item) for item in items]

@router.get("/types", response_model=List[str])
def get_item_types():
    """Get available item types"""
    return [item_type.value for item_type in ItemType]

@router.get("/measure-methods", response_model=List[str])
def get_measure_methods():
    """Get available measure methods"""
    return [method.value for method in MeasureMethod]

@router.get("/type/{item_type}", response_model=List[ItemResponse])
def get_items_by_type(item_type: str, db: Session = Depends(get_db)):
    """Get items by type"""
    try:
        item_type_enum = ItemType(item_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item type. Must be one of: {[t.value for t in ItemType]}"
        )
    
    items = item_crud.get_items_by_type(db, item_type_enum)
    return [item_crud.create_item_response(db, item) for item in items]

@router.get("/manufacturer/{manufacturer}", response_model=List[ItemResponse])
def get_items_by_manufacturer(manufacturer: str, db: Session = Depends(get_db)):
    """Get items by manufacturer"""
    items = item_crud.get_items_by_manufacturer(db, manufacturer)
    return [item_crud.create_item_response(db, item) for item in items]

@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: str, db: Session = Depends(get_db)):
    """Get item by ID"""
    item = item_crud.get_item(db, item_id=item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    return item_crud.create_item_response(db, item)

@router.get("/{item_id}/with-image", response_model=ItemWithImageResponse)
def get_item_with_image(item_id: str, db: Session = Depends(get_db)):
    """Get item with image data"""
    item_with_image = item_crud.get_item_image(db, item_id)
    if not item_with_image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    return item_with_image

@router.get("/{item_id}/stats", response_model=ItemStatsResponse)
def get_item_stats(item_id: str, db: Session = Depends(get_db)):
    """Get item with detailed statistics"""
    stats = item_crud.get_item_with_stats(db, item_id)
    if not stats:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    return stats

@router.post("/", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """Create new item"""
    try:
        created_item = item_crud.create_item(db=db, item=item)
        return item_crud.create_item_response(db, created_item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{item_id}", response_model=ItemResponse)
def update_item(item_id: str, item: ItemUpdate, db: Session = Depends(get_db)):
    """Update item"""
    try:
        updated_item = item_crud.update_item(db, item_id=item_id, item=item)
        if not updated_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        return item_crud.create_item_response(db, updated_item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{item_id}", response_model=ItemResponse)
def delete_item(item_id: str, db: Session = Depends(get_db)):
    """Delete item"""
    try:
        deleted_item = item_crud.delete_item(db, item_id=item_id)
        if not deleted_item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Item not found"
            )
        return item_crud.create_item_response(db, deleted_item)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/count/total", response_model=int)
def get_item_count(db: Session = Depends(get_db)):
    """Get total item count"""
    return item_crud.get_item_count(db)

@router.get("/count/type/{item_type}", response_model=int)
def get_item_count_by_type(item_type: str, db: Session = Depends(get_db)):
    """Get item count by type"""
    try:
        item_type_enum = ItemType(item_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid item type. Must be one of: {[t.value for t in ItemType]}"
        )
    
    return item_crud.get_item_count_by_type(db, item_type_enum)

@router.get("/count/manufacturers", response_model=int)
def get_manufacturer_count(db: Session = Depends(get_db)):
    """Get count of unique manufacturers"""
    return item_crud.get_manufacturer_count(db)