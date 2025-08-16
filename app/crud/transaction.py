from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, and_, func
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from app.models.transaction import Transaction, TransactionType, ItemType
from app.schemas.transaction import TransactionCreate, TransactionFilter

def create_transaction(db: Session, transaction: TransactionCreate) -> Transaction:
    """Create a new transaction"""
    db_transaction = Transaction(
        transaction_type=transaction.transaction_type,
        item_type=transaction.item_type,
        item_id=transaction.item_id,
        item_name=transaction.item_name,
        storage_section_id=transaction.storage_section_id,
        partition_id=transaction.partition_id,
        large_item_id=transaction.large_item_id,
        container_id=transaction.container_id,
        previous_quantity=transaction.previous_quantity,
        current_quantity=transaction.current_quantity,
        quantity_change=transaction.quantity_change,
        previous_weight=transaction.previous_weight,
        current_weight=transaction.current_weight,
        weight_change=transaction.weight_change, 
        user_name=transaction.user_name
    )
    
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

def get_transaction(db: Session, transaction_id: str) -> Optional[Transaction]:
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()

def get_transactions(db: Session, skip: int = 0, limit: int = 100, sort_by: str = "transaction_date", sort_order: str = "desc") -> List[Transaction]:
    query = db.query(Transaction)
    query = query.order_by(desc(getattr(Transaction, sort_by)) if sort_order.lower() == "desc" else asc(getattr(Transaction, sort_by)))
    return query.offset(skip).limit(limit).all()

def get_transactions_filtered(db: Session, filters: TransactionFilter, skip: int = 0, limit: int = 100, sort_by: str = "transaction_date", sort_order: str = "desc") -> tuple[List[Transaction], int]:
    query = db.query(Transaction)
    conditions = []
    
    if filters.transaction_types:
        conditions.append(Transaction.transaction_type.in_(filters.transaction_types))
    if filters.item_types:
        conditions.append(Transaction.item_type.in_(filters.item_types))
    if filters.item_ids:
        conditions.append(Transaction.item_id.in_(filters.item_ids))
    if filters.storage_section_ids:
        conditions.append(Transaction.storage_section_id.in_(filters.storage_section_ids))
    if filters.users:
        conditions.append(Transaction.user_name.in_(filters.users))
    if filters.start_date:
        conditions.append(Transaction.transaction_date >= filters.start_date)
    if filters.end_date:
        conditions.append(Transaction.transaction_date <= filters.end_date)
    
    if conditions:
        query = query.filter(and_(*conditions))
    
    total_count = query.count()
    query = query.order_by(desc(getattr(Transaction, sort_by)) if sort_order.lower() == "desc" else asc(getattr(Transaction, sort_by)))
    transactions = query.offset(skip).limit(limit).all()
    
    return transactions, total_count

def get_recent_transactions(db: Session, days: int = 7, limit: int = 50) -> List[Transaction]:
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    return db.query(Transaction)\
        .filter(Transaction.transaction_date >= cutoff_date)\
        .order_by(desc(Transaction.transaction_date))\
        .limit(limit)\
        .all()

def get_transactions_by_item(db: Session, item_id: str, skip: int = 0, limit: int = 10):
    query = db.query(Transaction).filter(Transaction.item_id == item_id)
    total_count = query.count()
    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions, total_count


def get_transactions_by_partition(db: Session, partition_id: str, skip: int = 0, limit: int = 10):
    query = db.query(Transaction).filter(Transaction.partition_id == partition_id)
    total_count = query.count()
    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions, total_count


def get_transactions_by_container(db: Session, container_id: str, skip: int = 0, limit: int = 10):
    query = db.query(Transaction).filter(Transaction.container_id == container_id)
    total_count = query.count()
    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions, total_count


def get_transactions_by_large_item(db: Session, large_item_id: str, skip: int = 0, limit: int = 10):
    query = db.query(Transaction).filter(Transaction.large_item_id == large_item_id)
    total_count = query.count()
    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions, total_count


def get_transactions_by_storage_section(db: Session, storage_section_id: str, skip: int = 0, limit: int = 10):
    query = db.query(Transaction).filter(Transaction.storage_section_id == storage_section_id)
    total_count = query.count()
    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions, total_count


def get_transactions_by_user(db: Session, user_name: str, skip: int = 0, limit: int = 10):
    query = db.query(Transaction).filter(Transaction.user_name == user_name)
    total_count = query.count()
    transactions = query.order_by(Transaction.transaction_date.desc()).offset(skip).limit(limit).all()
    return transactions, total_count

def get_transaction_count(db: Session) -> int:
    """Return total number of transactions"""
    return db.query(Transaction).count()

def get_transaction_stats(db: Session, filters: Optional[TransactionFilter] = None) -> Dict[str, Any]:
    query = db.query(Transaction)
    if filters:
        conditions = []
        if filters.transaction_types:
            conditions.append(Transaction.transaction_type.in_(filters.transaction_types))
        if filters.item_types:
            conditions.append(Transaction.item_type.in_(filters.item_types))
        if filters.start_date:
            conditions.append(Transaction.transaction_date >= filters.start_date)
        if filters.end_date:
            conditions.append(Transaction.transaction_date <= filters.end_date)
        if conditions:
            query = query.filter(and_(*conditions))
    
    total_transactions = query.count()
    withdrawals = query.filter(Transaction.transaction_type == TransactionType.WITHDRAW).count()
    returns = query.filter(Transaction.transaction_type == TransactionType.RETURN).count()
    consumed = query.filter(Transaction.transaction_type == TransactionType.CONSUMED).count()
    
    unique_items = query.with_entities(Transaction.item_id).distinct().count()
    unique_users = query.filter(Transaction.user_name.isnot(None)).with_entities(Transaction.user_name).distinct().count()
    
    # Quantity changes for partition returns only
    total_quantity_changes = db.query(func.coalesce(func.sum(Transaction.quantity_change), 0))\
        .filter(Transaction.item_type == ItemType.PARTITION, Transaction.transaction_type == TransactionType.RETURN)
    # Weight changes for container returns only
    total_weight_changes = db.query(func.coalesce(func.sum(Transaction.weight_change), 0.0))\
        .filter(Transaction.item_type == ItemType.CONTAINER, Transaction.transaction_type == TransactionType.RETURN)
    
    if filters:
        if filters.start_date:
            total_quantity_changes = total_quantity_changes.filter(Transaction.transaction_date >= filters.start_date)
            total_weight_changes = total_weight_changes.filter(Transaction.transaction_date >= filters.start_date)
        if filters.end_date:
            total_quantity_changes = total_quantity_changes.filter(Transaction.transaction_date <= filters.end_date)
            total_weight_changes = total_weight_changes.filter(Transaction.transaction_date <= filters.end_date)
    
    total_quantity_changes = total_quantity_changes.scalar()
    total_weight_changes = total_weight_changes.scalar()
    
    date_range = {}
    if total_transactions > 0:
        earliest = query.order_by(Transaction.transaction_date).first()
        latest = query.order_by(desc(Transaction.transaction_date)).first()
        date_range = {
            "earliest": earliest.transaction_date if earliest else None,
            "latest": latest.transaction_date if latest else None
        }
    
    return {
        "total_transactions": total_transactions,
        "withdrawals": withdrawals,
        "returns": returns,
        "consumed": consumed,
        "unique_items": unique_items,
        "unique_users": unique_users,
        "total_quantity_changes": total_quantity_changes,
        "total_weight_changes": total_weight_changes,
        "date_range": date_range
    }

def delete_transaction(db: Session, transaction_id: str) -> bool:
    transaction = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if transaction:
        db.delete(transaction)
        db.commit()
        return True
    return False
