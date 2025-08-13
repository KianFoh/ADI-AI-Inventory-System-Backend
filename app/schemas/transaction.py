from pydantic import BaseModel, field_validator, computed_field, model_validator
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

class TransactionCreate(BaseModel):
    transaction_type: TransactionType
    item_type: ItemType
    item_id: str
    item_name: str
    storage_section_id: str
    
    # ID fields based on item_type
    partition_id: Optional[str] = None
    large_item_id: Optional[str] = None
    container_id: Optional[str] = None
    
    # Quantity fields (for partition RETURNS only)
    previous_quantity: Optional[int] = None
    current_quantity: Optional[int] = None
    quantity_change: Optional[int] = None
    
    # Weight fields (for container RETURNS only)
    previous_weight: Optional[float] = None
    current_weight: Optional[float] = None
    weight_change: Optional[float] = None
    
    user_name: Optional[str] = None

    @model_validator(mode='after')
    def validate_transaction_fields(self):
        print(f"DEBUG: Validating transaction - item_type={self.item_type}, transaction_type={self.transaction_type}")
        
        if self.item_type == ItemType.PARTITION:
            self._validate_partition_transaction()
            
        elif self.item_type == ItemType.LARGE_ITEM:
            self._validate_large_item_transaction()
            
        elif self.item_type == ItemType.CONTAINER:
            self._validate_container_transaction()
        
        return self

    def _validate_partition_transaction(self):
        """Validate partition transaction"""
        # Required fields
        if self.partition_id is None:
            raise ValueError('partition_id is required for partition transactions')
        
        # Large item and container fields must be None
        if self.large_item_id is not None:
            raise ValueError('large_item_id should be None for partition transactions')
        if self.container_id is not None:
            raise ValueError('container_id should be None for partition transactions')
        
        # Weight fields must be None
        weight_fields = {
            'previous_weight': self.previous_weight,
            'current_weight': self.current_weight,
            'weight_change': self.weight_change
        }
        
        for field_name, value in weight_fields.items():
            if value is not None:
                raise ValueError(f'{field_name} should be None for partition transactions')
        
        if self.transaction_type == TransactionType.WITHDRAW:
            # WITHDRAW: No quantity tracking
            quantity_fields = {
                'previous_quantity': self.previous_quantity,
                'current_quantity': self.current_quantity,
                'quantity_change': self.quantity_change
            }
            
            for field_name, value in quantity_fields.items():
                if value is not None:
                    raise ValueError(f'{field_name} should be None for partition withdrawal transactions')
        
        elif self.transaction_type == TransactionType.RETURN:
            # RETURN: Must have quantity tracking
            required_fields = {
                'previous_quantity': self.previous_quantity,
                'current_quantity': self.current_quantity,
                'quantity_change': self.quantity_change
            }
            
            for field_name, value in required_fields.items():
                if value is None:
                    raise ValueError(f'{field_name} is required for partition return transactions')

    def _validate_large_item_transaction(self):
        """Validate large item transaction - NO quantity or weight tracking ever"""
        # Required fields
        if self.large_item_id is None:
            raise ValueError('large_item_id is required for large item transactions')
        
        # Forbidden fields
        forbidden_fields = {
            'partition_id': self.partition_id,
            'container_id': self.container_id,
            'previous_quantity': self.previous_quantity,
            'current_quantity': self.current_quantity,
            'quantity_change': self.quantity_change,
            'previous_weight': self.previous_weight,
            'current_weight': self.current_weight,
            'weight_change': self.weight_change
        }
        
        for field_name, value in forbidden_fields.items():
            if value is not None:
                raise ValueError(f'{field_name} should be None for large item transactions')

    def _validate_container_transaction(self):
        """Validate container transaction"""
        # Required fields
        if self.container_id is None:
            raise ValueError('container_id is required for container transactions')
        
        # Partition and large item fields must be None
        if self.partition_id is not None:
            raise ValueError('partition_id should be None for container transactions')
        if self.large_item_id is not None:
            raise ValueError('large_item_id should be None for container transactions')
        
        # Quantity fields must be None
        quantity_fields = {
            'previous_quantity': self.previous_quantity,
            'current_quantity': self.current_quantity,
            'quantity_change': self.quantity_change
        }
        
        for field_name, value in quantity_fields.items():
            if value is not None:
                raise ValueError(f'{field_name} should be None for container transactions')
        
        if self.transaction_type == TransactionType.WITHDRAW:
            # WITHDRAW: No weight tracking
            weight_fields = {
                'previous_weight': self.previous_weight,
                'current_weight': self.current_weight,
                'weight_change': self.weight_change
            }
            
            for field_name, value in weight_fields.items():
                if value is not None:
                    raise ValueError(f'{field_name} should be None for container withdrawal transactions')
        
        elif self.transaction_type == TransactionType.RETURN:
            # RETURN: Must have weight tracking
            required_fields = {
                'previous_weight': self.previous_weight,
                'current_weight': self.current_weight,
                'weight_change': self.weight_change
            }
            
            for field_name, value in required_fields.items():
                if value is None:
                    raise ValueError(f'{field_name} is required for container return transactions')

# Clean response without computed fields
class TransactionResponse(TransactionBase):
    id: str
    transaction_date: datetime
    
    # Include all fields
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
    unique_items: int
    unique_users: int
    total_quantity_changes: int
    total_weight_changes: float
    date_range: dict