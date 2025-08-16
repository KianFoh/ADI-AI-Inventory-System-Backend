from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import item as item_crud
from app.models.item import ItemType, MeasureMethod
from app.schemas.item import (
    ItemCreate, 
    ItemUpdate, 
    ItemResponse,
    ItemStatsResponse,
    PaginatedItemsResponse
)
from app.utils.image import get_image_full_path

router = APIRouter(
    prefix="/items",
    tags=["items"]
)

def get_base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


# ------------------ List & Search ------------------ #

@router.get("/", response_model=PaginatedItemsResponse)
def get_items(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    item_type: Optional[str] = None,
    manufacturer: Optional[str] = None,
    db: Session = Depends(get_db)
):
    # Convert string to enum
    item_type_enum = None
    if item_type:
        try:
            item_type_enum = ItemType(item_type.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid item type. Must be one of {[t.value for t in ItemType]}")

    items, total_count = item_crud.get_items(
        db, page=page, page_size=page_size, search=search,
        item_type=item_type_enum, manufacturer=manufacturer
    )

    base_url = get_base_url(request)
    item_responses = [item_crud.create_item_response(db, item, base_url) for item in items]

    return PaginatedItemsResponse.create(
        items=item_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/search", response_model=List[ItemResponse])
def search_items(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    items = item_crud.search_items_by_keyword(db, keyword=q, limit=limit)
    base_url = get_base_url(request)
    return [item_crud.create_item_response(db, item, base_url) for item in items]



# ------------------ Item Types & Measure Methods ------------------ #

@router.get("/types", response_model=List[str])
def get_item_types():
    return [t.value for t in ItemType]

@router.get("/measure-methods", response_model=List[str])
def get_measure_methods():
    return [m.value for m in MeasureMethod]

# ------------------ Single Item ------------------ #

@router.get("/{item_id}", response_model=ItemResponse)
def get_item(request: Request, item_id: str, db: Session = Depends(get_db)):
    item = item_crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    base_url = get_base_url(request)
    return item_crud.create_item_response(db, item, base_url)

@router.get("/{item_id}/stats", response_model=ItemStatsResponse)
def get_item_stats(request: Request, item_id: str, db: Session = Depends(get_db)):
    base_url = get_base_url(request)
    stats = item_crud.get_item_with_stats(db, item_id, base_url)
    if not stats:
        raise HTTPException(status_code=404, detail="Item not found")
    return stats


# ------------------ Item Images ------------------ #

@router.get("/{item_id}/image")
def get_item_image(item_id: str, db: Session = Depends(get_db)):
    item = item_crud.get_item(db, item_id)
    if not item or not item.image_path:
        raise HTTPException(status_code=404, detail="Image not found")
    image_path = get_image_full_path(item.image_path)
    if not image_path:
        raise HTTPException(status_code=404, detail="Image file not found")
    return FileResponse(image_path)


# ------------------ Filter by Type / Manufacturer ------------------ #

@router.get("/type/{item_type}", response_model=List[ItemResponse])
def get_items_by_type(request: Request, item_type: str, db: Session = Depends(get_db)):
    try:
        item_type_enum = ItemType(item_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid item type. Must be one of {[t.value for t in ItemType]}")
    items = item_crud.get_items_by_type(db, item_type_enum)
    base_url = get_base_url(request)
    return [item_crud.create_item_response(db, item, base_url) for item in items]

@router.get("/manufacturer/{manufacturer}", response_model=List[ItemResponse])
def get_items_by_manufacturer(request: Request, manufacturer: str, db: Session = Depends(get_db)):
    items = item_crud.get_items_by_manufacturer(db, manufacturer)
    base_url = get_base_url(request)
    return [item_crud.create_item_response(db, item, base_url) for item in items]


# ------------------ Create / Update / Delete ------------------ #

@router.post("/", response_model=ItemResponse, status_code=201)
def create_item(request: Request, item: ItemCreate, db: Session = Depends(get_db)):
    try:
        created_item = item_crud.create_item(db, item)
        base_url = get_base_url(request)
        return item_crud.create_item_response(db, created_item, base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{item_id}", response_model=ItemResponse)
def update_item(request: Request, item_id: str, item: ItemUpdate, db: Session = Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    try:
        updated_item = item_crud.update_item(db, item_id, item)
        if not updated_item:
            raise HTTPException(status_code=404, detail="Item not found")
        base_url = get_base_url(request)
        return item_crud.create_item_response(db, updated_item, base_url)
    except IntegrityError as e:
        if "violates foreign key constraint" in str(e):
            raise HTTPException(status_code=400, detail="Cannot update or delete item: it is still referenced by partitions, large items, or containers.")
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{item_id}", response_model=ItemResponse)
def delete_item(request: Request, item_id: str, db: Session = Depends(get_db)):
    try:
        deleted_item = item_crud.delete_item(db, item_id)
        if not deleted_item:
            raise HTTPException(status_code=404, detail="Item not found")
        base_url = get_base_url(request)
        return item_crud.create_item_response(db, deleted_item, base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ------------------ Counts ------------------ #

@router.get("/count/total", response_model=int)
def get_item_count(db: Session = Depends(get_db)):
    return item_crud.get_item_count(db)

@router.get("/count/type/{item_type}", response_model=int)
def get_item_count_by_type(item_type: str, db: Session = Depends(get_db)):
    try:
        item_type_enum = ItemType(item_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid item type. Must be one of {[t.value for t in ItemType]}")
    return item_crud.get_item_count_by_type(db, item_type_enum)

@router.get("/count/manufacturers", response_model=int)
def get_manufacturer_count(db: Session = Depends(get_db)):
    return item_crud.get_manufacturer_count(db)
