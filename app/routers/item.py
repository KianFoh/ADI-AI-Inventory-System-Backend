from operator import and_
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import distinct, func
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
from app.database import get_db
from app.crud import item as item_crud
from app.models.item import ItemStatHistory, ItemType, MeasureMethod, StockStatus
from app.schemas.item import (
    ItemCreate, 
    ItemUpdate, 
    ItemResponse,
    ItemStatsResponse,
    PaginatedItemsResponse
)
from app.utils.image import get_image_full_path
import re
from datetime import datetime, date, time, timedelta
import calendar
import logging
import traceback

def _period_bounds_for(granularity: str, start_dt: date, idx: int):
    """
    Return (period_start_datetime, period_end_datetime, period_label_date) for the idx-th period
    starting at start_dt. Supports 'day', 'month', 'year'.
    """
    if granularity == "day":
        cur = start_dt + timedelta(days=idx)
        start_dt_time = datetime.combine(cur, time.min)
        end_dt_time = datetime.combine(cur, time.max)
        label = cur
    elif granularity == "month":
        y = start_dt.year + (start_dt.month - 1 + idx) // 12
        m = (start_dt.month - 1 + idx) % 12 + 1
        label = date(y, m, 1)
        start_dt_time = datetime.combine(label, time.min)
        last_day = calendar.monthrange(y, m)[1]
        end_dt_time = datetime.combine(date(y, m, last_day), time.max)
    elif granularity == "year":
        y = start_dt.year + idx
        label = date(y, 1, 1)
        start_dt_time = datetime.combine(label, time.min)
        end_dt_time = datetime.combine(date(y, 12, 31), time.max)
    else:
        raise ValueError("unsupported granularity")
    return start_dt_time, end_dt_time, label

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
    stock_status: Optional[str] = None,
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
        item_type=item_type_enum, manufacturer=manufacturer, stock_status=stock_status
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

# ------------------ Counts & Overview (must appear BEFORE the dynamic /{item_id} route) ------------------ #
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

@router.get("/overview", response_model=dict)
def items_overview(db: Session = Depends(get_db)):
    try:
        overview = item_crud.get_items_overview(db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to compute items overview")
    return overview

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

        # Determine resulting process (uppercase, no spaces)
        resulting_process = proc.strip().upper() if proc is not None else (db_item.process or "")

        # Determine name part (use new name if provided, otherwise extract existing name part)
        if name_val is not None:
            # Use the provided name, but strip any leading "<SOMETHING>-" prefix so we don't duplicate process
            raw_name = name_val.strip()
            if "-" in raw_name:
                name_part = raw_name.split("-", 1)[1].strip()
            else:
                name_part = raw_name
        else:
            # existing stored name is expected to be "{PROCESS}-{name_part}"
            # Remove any existing leading "<SOMETHING>-" prefix so we replace it
            if "-" in db_item.name:
                name_part = db_item.name.split("-", 1)[1].strip()
            else:
                name_part = db_item.name.strip()

        # Compose stored name same as create: "{PROCESS}-{name_part}" (omit leading hyphen if no process)
        if resulting_process:
            stored_name = f"{resulting_process}-{name_part}"
        else:
            stored_name = name_part

        update_payload["name"] = stored_name
        update_payload["process"] = resulting_process

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
    

# ------------------ Item Status History ------------------ #

@router.get("/history/aggregate", response_model=List[Dict[str, Any]])
def aggregate_item_status_history(
    start: str = Query(..., description="ISO date/time start (YYYY-MM-DD or ISO)"),
    end: str = Query(..., description="ISO date/time end (YYYY-MM-DD or ISO)"),
    granularity: str = Query("day", description="Aggregation granularity: day|month|year"),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    try:
        points = item_crud.aggregate_item_status_history(db, start=start, end=end, granularity=granularity)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logging.exception("aggregate_item_status_history failed")
        # include traceback in logs, return message for local debugging
        tb = traceback.format_exc()
        logging.debug(tb)
        # For production do not leak internals; here we return message to help debug locally
        raise HTTPException(status_code=500, detail=f"Failed to aggregate item status history: {e}")
    return points


