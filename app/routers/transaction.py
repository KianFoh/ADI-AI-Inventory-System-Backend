from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.database import get_db
from app.crud import transaction as transaction_crud
from app.schemas.transaction import (
    TransactionCreate, 
    TransactionResponse,
    PaginatedTransactionsResponse,
    TransactionFilter,
    TransactionStats
)
from app.models.transaction import TransactionType, ItemType
import io
import csv
from datetime import datetime as _dt
from fastapi.responses import StreamingResponse

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"]
)

def _paginate_response(transactions, total_count, page, page_size):
    transaction_responses = [TransactionResponse.model_validate(txn, from_attributes=True) for txn in transactions]
    return PaginatedTransactionsResponse.create(
        transactions=transaction_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/", response_model=PaginatedTransactionsResponse)
def get_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("transaction_date"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    search: Optional[str] = Query(None, description="Keyword to match item id, item name, unit id or user name"),
    start_date: Optional[datetime] = Query(None, description="Filter transactions from this datetime (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Filter transactions up to this datetime (inclusive)"),
    transaction_types: Optional[List[TransactionType]] = Query(None, description="Filter by transaction types"),
    item_types: Optional[List[ItemType]] = Query(None, description="Filter by item types"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size

    # If any filter/search provided use the filtered CRUD which returns (transactions, total_count)
    if any([search, start_date, end_date, transaction_types, item_types]):
        filters = TransactionFilter(
            search=search,
            start_date=start_date,
            end_date=end_date,
            transaction_types=transaction_types,
            item_types=item_types
        )
        transactions, total_count = transaction_crud.get_transactions_filtered(
            db,
            filters=filters,
            skip=skip,
            limit=page_size,
            sort_by=sort_by,
            sort_order=sort_order
        )
    else:
        transactions = transaction_crud.get_transactions(db, skip=skip, limit=page_size, sort_by=sort_by, sort_order=sort_order)
        total_count = transaction_crud.get_transaction_count(db)

    return _paginate_response(transactions, total_count, page, page_size)

# Total count
@router.get("/count/total", response_model=int)
def get_transaction_count(db: Session = Depends(get_db)):
    return transaction_crud.get_transaction_count(db)

@router.get("/export")
def export_transactions_csv(
    sort_by: str = Query("transaction_date"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    search: Optional[str] = Query(None, description="Keyword to match item id, item name, unit id or user name"),
    start_date: Optional[datetime] = Query(None, description="Filter transactions from this datetime (inclusive)"),
    end_date: Optional[datetime] = Query(None, description="Filter transactions up to this datetime (inclusive)"),
    transaction_types: Optional[List[TransactionType]] = Query(None, description="Filter by transaction types"),
    item_types: Optional[List[ItemType]] = Query(None, description="Filter by item types"),
    db: Session = Depends(get_db),
):
    """
    Export transactions matching the same filters as the list endpoint.
    Returns a streaming CSV attachment.
    """
    filters = None
    if any([search, start_date, end_date, transaction_types, item_types]):
        filters = TransactionFilter(
            search=search,
            start_date=start_date,
            end_date=end_date,
            transaction_types=transaction_types,
            item_types=item_types
        )

    rows = transaction_crud.get_transactions_for_export(db, filters=filters, sort_by=sort_by, sort_order=sort_order)

    headers = [
        "id", "transaction_date", "transaction_type", "item_type", "item_id", "item_name",
        "unit_id", "partition_id", "large_item_id", "container_id", "storage_section_id",
        "user_name", "previous_quantity", "current_quantity", "quantity_change",
        "previous_weight", "current_weight", "weight_change", "notes"
    ]

    def iter_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(headers)
        yield buf.getvalue()
        buf.seek(0); buf.truncate(0)
        for r in rows:
            out = [r.get(h, "") for h in headers]
            writer.writerow(out)
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)

    stamp = _dt.utcnow().strftime("%Y%m%dT%H%M%SZ")
    filename = f"transactions_{stamp}.csv"
    return StreamingResponse(iter_csv(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})

@router.post("/filter", response_model=PaginatedTransactionsResponse)
def get_filtered_transactions(
    filters: TransactionFilter,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    sort_by: str = Query("transaction_date"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    skip = (page - 1) * page_size
    transactions, total_count = transaction_crud.get_transactions_filtered(db, filters=filters, skip=skip, limit=page_size, sort_by=sort_by, sort_order=sort_order)
    return _paginate_response(transactions, total_count, page, page_size)

@router.get("/recent", response_model=List[TransactionResponse])
def get_recent_transactions(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    transactions = transaction_crud.get_recent_transactions(db, days=days, limit=limit)
    return [TransactionResponse.model_validate(txn, from_attributes=True) for txn in transactions]

@router.get("/stats", response_model=TransactionStats)
def get_transaction_statistics(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    transaction_types: Optional[List[TransactionType]] = Query(None),
    item_types: Optional[List[ItemType]] = Query(None),
    db: Session = Depends(get_db)
):
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date,
        transaction_types=transaction_types,
        item_types=item_types
    )
    stats_data = transaction_crud.get_transaction_stats(db, filters)
    return TransactionStats(**stats_data)

# Generic helper for paginated "by_*" queries
def _get_transactions_by_field(field_name: str, value: str, page: int, page_size: int, db: Session):
    skip = (page - 1) * page_size
    crud_map = {
        "item_id": transaction_crud.get_transactions_by_item,
        "partition_id": transaction_crud.get_transactions_by_partition,
        "container_id": transaction_crud.get_transactions_by_container,
        "large_item_id": transaction_crud.get_transactions_by_large_item,
        "storage_section_id": transaction_crud.get_transactions_by_storage_section,
        "user_name": transaction_crud.get_transactions_by_user
    }
    if field_name not in crud_map:
        raise HTTPException(status_code=400, detail={"field": field_name, "message": "Invalid field for filtering"})
    transactions, total_count = crud_map[field_name](db, value, skip=skip, limit=page_size)
    return [TransactionResponse.model_validate(txn, from_attributes=True) for txn in transactions]

# By-field endpoints
@router.get("/item/{item_id}", response_model=List[TransactionResponse])
def get_transactions_by_item(item_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return _get_transactions_by_field("item_id", item_id, page, page_size, db)

@router.get("/partition/{partition_id}", response_model=List[TransactionResponse])
def get_transactions_by_partition(partition_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return _get_transactions_by_field("partition_id", partition_id, page, page_size, db)

@router.get("/container/{container_id}", response_model=List[TransactionResponse])
def get_transactions_by_container(container_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return _get_transactions_by_field("container_id", container_id, page, page_size, db)

@router.get("/large-item/{large_item_id}", response_model=List[TransactionResponse])
def get_transactions_by_large_item(large_item_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return _get_transactions_by_field("large_item_id", large_item_id, page, page_size, db)

@router.get("/storage/{storage_section_id}", response_model=List[TransactionResponse])
def get_transactions_by_storage_section(storage_section_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return _get_transactions_by_field("storage_section_id", storage_section_id, page, page_size, db)

@router.get("/user/{user_name}", response_model=List[TransactionResponse])
def get_transactions_by_user(user_name: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    return _get_transactions_by_field("user_name", user_name, page, page_size, db)

# Single transaction
@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    transaction = transaction_crud.get_transaction(db, transaction_id=transaction_id)
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"field": "transaction_id", "message": "Transaction not found"})
    return TransactionResponse.model_validate(transaction, from_attributes=True)

# Bulk create transactions
@router.post("/bulk", response_model=List[TransactionResponse], status_code=status.HTTP_201_CREATED)
def create_transactions_bulk(
    transactions: List[TransactionCreate] = Body(...),
    db: Session = Depends(get_db)
):
    """Create multiple transactions in a single API call"""
    created_transactions = []

    for txn in transactions:
        created_txn = transaction_crud.create_transaction(db=db, transaction=txn)
        created_transactions.append(TransactionResponse.model_validate(created_txn, from_attributes=True))

    return created_transactions

# Create transaction
@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    created_transaction = transaction_crud.create_transaction(db=db, transaction=transaction)
    return TransactionResponse.model_validate(created_transaction, from_attributes=True)

# Delete transaction
@router.delete("/{transaction_id}", response_model=dict)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    deleted = transaction_crud.delete_transaction(db, transaction_id=transaction_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"field": "transaction_id", "message": "Transaction not found"})
    return {"message": "Transaction deleted successfully"}


