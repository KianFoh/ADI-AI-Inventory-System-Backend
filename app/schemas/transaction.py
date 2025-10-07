from pydantic import BaseModel, Field, model_validator
from typing import Optional, List
from datetime import datetime
import math
from app.models.transaction import TransactionType, ItemType

class TransactionBase(BaseModel):
    transaction_type: TransactionType
    item_type: ItemType
    item_id: str
    item_name: str
    storage_section_id: str
    user_name: Optional[str] = None

class TransactionCreate(TransactionBase):
    # ID fields based on item_type
    partition_id: Optional[str] = Field(None, max_length=20)
    large_item_id: Optional[str] = Field(None, max_length=20)
    container_id: Optional[str] = Field(None, max_length=20)

    # Quantity fields
    previous_quantity: Optional[int] = None
    current_quantity: Optional[int] = None
    quantity_change: Optional[int] = None

    # Weight fields (for container RETURN)
    previous_weight: Optional[float] = None
    current_weight: Optional[float] = None
    weight_change: Optional[float] = None

    @model_validator(mode='after')
    def validate_transaction_fields(self):
        # Partition validation
        if self.item_type == ItemType.PARTITION:
            if not self.partition_id:
                raise ValueError("partition_id is required for partition transactions")
            if self.large_item_id or self.container_id:
                raise ValueError("Only partition_id should be set for partition transactions")

            if self.transaction_type == TransactionType.RETURN:
                required_fields = ['previous_quantity', 'current_quantity', 'quantity_change']
                for f in required_fields:
                    if getattr(self, f) is None:
                        raise ValueError(f"{f} is required for partition return transactions")

            # Partition cannot have weight
            for f in ['previous_weight', 'current_weight', 'weight_change']:
                if getattr(self, f) is not None:
                    raise ValueError(f"{f} should be None for partition transactions")

        # Container validation
        elif self.item_type == ItemType.CONTAINER:
            if not self.container_id:
                raise ValueError("container_id is required for container transactions")
            if self.partition_id or self.large_item_id:
                raise ValueError("Only container_id should be set for container transactions")

            # Weight is required for RETURN
            if self.transaction_type == TransactionType.RETURN:
                for f in ['previous_weight', 'current_weight', 'weight_change']:
                    if getattr(self, f) is None:
                        raise ValueError(f"{f} is required for container return transactions")
            # Quantity optional, no restriction

        # Large item validation
        elif self.item_type == ItemType.LARGE_ITEM:
            if not self.large_item_id:
                raise ValueError("large_item_id is required for large item transactions")
            forbidden_fields = [
                'partition_id', 'container_id',
                'previous_quantity', 'current_quantity', 'quantity_change',
                'previous_weight', 'current_weight', 'weight_change'
            ]
            for f in forbidden_fields:
                if getattr(self, f) is not None:
                    raise ValueError(f"{f} should be None for large item transactions")

        return self


class TransactionResponse(TransactionBase):
    id: str
    transaction_date: datetime

    partition_id: Optional[str] = None
    large_item_id: Optional[str] = None
    container_id: Optional[str] = None
    previous_quantity: Optional[int] = None
    current_quantity: Optional[int] = None
    quantity_change: Optional[int] = None
    previous_weight: Optional[float] = None
    current_weight: Optional[float] = None
    weight_change: Optional[float] = None

    class Config:
        from_attributes = True


class PaginatedTransactionsResponse(BaseModel):
    transactions: List[TransactionResponse]
    total_transactions: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, transactions: List[TransactionResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        return cls(
            transactions=transactions,
            total_transactions=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )


class TransactionFilter(BaseModel):
    transaction_types: Optional[List[TransactionType]] = None
    item_types: Optional[List[ItemType]] = None
    item_ids: Optional[List[str]] = None
    storage_section_ids: Optional[List[str]] = None
    users: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class TransactionStats(BaseModel):
    total_transactions: int
    withdrawals: int
    returns: int
    consumed: int
    registrations: int
    unique_items: int
    unique_users: int
    total_quantity_changes: int
    total_weight_changes: float
    date_range: dict
