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
import re

router = APIRouter(
    prefix="/items",
    tags=["items"]
)

def get_base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


# ------------------ List & Search ------------------ #

@router.get("/", response_model=PaginatedItemsResponse, response_model_exclude_none=True)
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
            raise HTTPException(status_code=400, detail={"field": "item_type", "message": f"Invalid item type. Must be one of {[t.value for t in ItemType]}"})

    items, total_count = item_crud.get_items(
        db, page=page, page_size=page_size, search=search,
        item_type=item_type_enum, manufacturer=manufacturer
    )

    base_url = get_base_url(request)
    # use CRUD helper that returns ItemStatsResponse (type-specific extra fields)
    item_responses = [item_crud.build_item_with_stats(db, item, base_url) for item in items]

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

@router.get("/{item_id}", response_model=ItemStatsResponse, response_model_exclude_none=True)
def get_item(request: Request, item_id: str, db: Session = Depends(get_db)):
    item = item_crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail={"field": "item_id", "message": "Item not found"})
    base_url = get_base_url(request)
    return item_crud.build_item_with_stats(db, item, base_url)

@router.get("/{item_id}/stats", response_model=ItemStatsResponse, response_model_exclude_none=True)
def get_item_stats(request: Request, item_id: str, db: Session = Depends(get_db)):
    item = item_crud.get_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail={"field": "item_id", "message": "Item not found"})
    base_url = get_base_url(request)
    return item_crud.build_item_with_stats(db, item, base_url)


# ------------------ Item Images ------------------ #

@router.get("/{item_id}/image")
def get_item_image(item_id: str, db: Session = Depends(get_db)):
    item = item_crud.get_item(db, item_id)
    if not item or not item.image_path:
        raise HTTPException(status_code=404, detail={"field": "item_id", "message": "Image not found"})
    image_path = get_image_full_path(item.image_path)
    if not image_path:
        raise HTTPException(status_code=404, detail={"field": "item_id", "message": "Image file not found"})
    return FileResponse(image_path)


# ------------------ Filter by Type / Manufacturer ------------------ #

@router.get("/type/{item_type}", response_model=List[ItemResponse])
def get_items_by_type(request: Request, item_type: str, db: Session = Depends(get_db)):
    try:
        item_type_enum = ItemType(item_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail={"field": "item_type", "message": f"Invalid item type. Must be one of {[t.value for t in ItemType]}"})
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
    # process validated by schema; ensure uppercase and no spaces
    process = item.process.strip().upper()
    # combine for stored name
    stored_name = f"{process}-{item.name.strip()}"
    # prepare dict payload (we combine name but keep process separate)
    payload = item.model_dump()
    payload["name"] = stored_name
    payload["process"] = process

    try:
        created_item = item_crud.create_item(db, payload)
    except ValueError as e:
        # normalize ValueError payloads into a list of error dicts (or single string)
        err = e.args[0] if e.args else str(e)
        if isinstance(err, list):
            detail = err
        elif isinstance(err, dict):
            detail = [err]
        else:
            detail = {"message": str(err)}
        raise HTTPException(status_code=400, detail=detail)

    base_url = get_base_url(request)
    return item_crud.create_item_response(db, created_item, base_url)

@router.put("/{item_id}", response_model=ItemResponse)
def update_item(request: Request, item_id: str, item: ItemUpdate, db: Session = Depends(get_db)):
    update_payload = item.model_dump(exclude_unset=True)

    # If process/name present, combine to stored name
    proc = update_payload.get("process")
    name_val = update_payload.get("name")
    if proc is not None or name_val is not None:
        db_item = item_crud.get_item(db, item_id)
        if not db_item:
            raise HTTPException(status_code=404, detail={"field": "item_id", "message": "Item not found"})
        current_process = proc.strip().upper() if proc is not None else (db_item.process or "")
        current_name_part = name_val.strip() if name_val is not None else db_item.name[len(current_process):] if db_item.name.startswith(current_process) else db_item.name
        update_payload["name"] = f"{current_process}{current_name_part}"
        update_payload["process"] = current_process

    try:
        updated_item = item_crud.update_item(db, item_id, update_payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=e.args[0] if isinstance(e, ValueError) else str(e))
    base_url = get_base_url(request)
    return item_crud.create_item_response(db, updated_item, base_url)

@router.delete("/{item_id}", response_model=ItemResponse)
def delete_item(request: Request, item_id: str, db: Session = Depends(get_db)):
    try:
        deleted_item = item_crud.delete_item(db, item_id)
        if not deleted_item:
            raise HTTPException(status_code=404, detail={"field": "item_id", "message": "Item not found"})
        base_url = get_base_url(request)
        return item_crud.create_item_response(db, deleted_item, base_url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"field": "item_id", "message": str(e)})


# ------------------ Counts ------------------ #

@router.get("/count/total", response_model=int)
def get_item_count(db: Session = Depends(get_db)):
    return item_crud.get_item_count(db)

@router.get("/count/type/{item_type}", response_model=int)
def get_item_count_by_type(item_type: str, db: Session = Depends(get_db)):
    try:
        item_type_enum = ItemType(item_type.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail={"field": "item_type", "message": f"Invalid item type. Must be one of {[t.value for t in ItemType]}"})
    return item_crud.get_item_count_by_type(db, item_type_enum)

@router.get("/count/manufacturers", response_model=int)
def get_manufacturer_count(db: Session = Depends(get_db)):
    return item_crud.get_manufacturer_count(db)
