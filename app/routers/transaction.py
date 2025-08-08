from fastapi import APIRouter, Depends, HTTPException, status, Query
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

router = APIRouter(
    prefix="/transactions",
    tags=["transactions"]
)

@router.get("/", response_model=PaginatedTransactionsResponse)
def get_transactions(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("transaction_date", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """Get transactions with pagination"""
    skip = (page - 1) * page_size
    transactions = transaction_crud.get_transactions(
        db, 
        skip=skip, 
        limit=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    total_count = transaction_crud.get_transaction_count(db)
    transaction_responses = [TransactionResponse.model_validate(txn) for txn in transactions]
    
    return PaginatedTransactionsResponse.create(
        transactions=transaction_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.post("/filter", response_model=PaginatedTransactionsResponse)
def get_filtered_transactions(
    filters: TransactionFilter,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("transaction_date", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    db: Session = Depends(get_db)
):
    """Get filtered transactions with pagination"""
    skip = (page - 1) * page_size
    transactions, total_count = transaction_crud.get_transactions_filtered(
        db,
        filters=filters,
        skip=skip,
        limit=page_size,
        sort_by=sort_by,
        sort_order=sort_order
    )
    
    transaction_responses = [TransactionResponse.model_validate(txn) for txn in transactions]
    
    return PaginatedTransactionsResponse.create(
        transactions=transaction_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/recent", response_model=List[TransactionResponse])
def get_recent_transactions(
    days: int = Query(7, ge=1, le=30, description="Number of days back"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Get recent transactions"""
    transactions = transaction_crud.get_recent_transactions(db, days=days, limit=limit)
    return [TransactionResponse.model_validate(txn) for txn in transactions]

@router.get("/stats", response_model=TransactionStats)
def get_transaction_statistics(
    start_date: Optional[datetime] = Query(None, description="Start date filter"),
    end_date: Optional[datetime] = Query(None, description="End date filter"),
    transaction_types: Optional[List[TransactionType]] = Query(None, description="Transaction type filter"),
    item_types: Optional[List[ItemType]] = Query(None, description="Item type filter"),
    db: Session = Depends(get_db)
):
    """Get transaction statistics"""
    filters = TransactionFilter(
        start_date=start_date,
        end_date=end_date,
        transaction_types=transaction_types,
        item_types=item_types
    )
    
    stats_data = transaction_crud.get_transaction_stats(db, filters)
    return TransactionStats(**stats_data)

@router.get("/item/{item_id}", response_model=List[TransactionResponse])
def get_transactions_by_item(
    item_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get all transactions for a specific item"""
    skip = (page - 1) * page_size
    transactions = transaction_crud.get_transactions_by_item(
        db, 
        item_id=item_id, 
        skip=skip, 
        limit=page_size
    )
    return [TransactionResponse.model_validate(txn) for txn in transactions]

@router.get("/partition/{partition_id}", response_model=List[TransactionResponse])
def get_transactions_by_partition(
    partition_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get all transactions for a specific partition"""
    skip = (page - 1) * page_size
    transactions = transaction_crud.get_transactions_by_partition(
        db, 
        partition_id=partition_id, 
        skip=skip, 
        limit=page_size
    )
    return [TransactionResponse.model_validate(txn) for txn in transactions]

@router.get("/large-item/{large_item_id}", response_model=List[TransactionResponse])
def get_transactions_by_large_item(
    large_item_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get all transactions for a specific large item"""
    skip = (page - 1) * page_size
    transactions = transaction_crud.get_transactions_by_large_item(
        db, 
        large_item_id=large_item_id, 
        skip=skip, 
        limit=page_size
    )
    return [TransactionResponse.model_validate(txn) for txn in transactions]

@router.get("/storage/{storage_section_id}", response_model=List[TransactionResponse])
def get_transactions_by_storage_section(
    storage_section_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get all transactions for a specific storage section"""
    skip = (page - 1) * page_size
    transactions = transaction_crud.get_transactions_by_storage_section(
        db, 
        storage_section_id=storage_section_id, 
        skip=skip, 
        limit=page_size
    )
    return [TransactionResponse.model_validate(txn) for txn in transactions]

@router.get("/user/{user_name}", response_model=List[TransactionResponse])
def get_transactions_by_user(
    user_name: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """Get all transactions by a specific user"""
    skip = (page - 1) * page_size
    transactions = transaction_crud.get_transactions_by_user(
        db, 
        user_name=user_name, 
        skip=skip, 
        limit=page_size
    )
    return [TransactionResponse.model_validate(txn) for txn in transactions]

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Get transaction by ID"""
    transaction = transaction_crud.get_transaction(db, transaction_id=transaction_id)
    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    return TransactionResponse.model_validate(transaction)

@router.post("/", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(transaction: TransactionCreate, db: Session = Depends(get_db)):
    """Create new transaction"""
    created_transaction = transaction_crud.create_transaction(db=db, transaction=transaction)
    return TransactionResponse.model_validate(created_transaction)

@router.delete("/{transaction_id}", response_model=dict)
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Delete transaction (admin only)"""
    deleted = transaction_crud.delete_transaction(db, transaction_id=transaction_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )
    return {"message": "Transaction deleted successfully"}

@router.get("/count/total", response_model=int)
def get_transaction_count(db: Session = Depends(get_db)):
    """Get total transaction count"""
    return transaction_crud.get_transaction_count(db)