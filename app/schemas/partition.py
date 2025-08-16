from pydantic import BaseModel, field_validator
from typing import Optional, List
import math
from app.models.partition import PartitionStatus
from app.validators import (
    non_empty_string_validator,
    bounded_int_validator,
    bounded_int_optional_validator
)

class PartitionBase(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str
    quantity: int
    status: PartitionStatus = PartitionStatus.AVAILABLE

class PartitionCreate(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str
    quantity: int

    @field_validator('item_id')
    @classmethod
    def validate_item_id(cls, v: str) -> str:
        return non_empty_string_validator('Item ID')(v)

    @field_validator('storage_section_id')
    @classmethod
    def validate_storage_section_id(cls, v: str) -> str:
        return non_empty_string_validator('Storage Section ID')(v)

    @field_validator('rfid_tag_id')
    @classmethod
    def validate_rfid_tag_id(cls, v: str) -> str:
        return non_empty_string_validator('RFID Tag ID')(v)

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int, info) -> int:
        v = bounded_int_validator(0, 10000, 'Quantity')(v)
        item_id = info.data.get('item_id')
        if item_id:
            from app.models.item import Item
            from app.database import SessionLocal
            db = SessionLocal()
            item = db.query(Item).filter(Item.id == item_id).first()
            db.close()
            if not item:
                raise ValueError(f"Item '{item_id}' not found for partition validation.")
            if item.partition_capacity is None:
                raise ValueError(f"Item '{item_id}' does not have a partition_capacity set.")
            if v > item.partition_capacity:
                raise ValueError(f"Quantity ({v}) cannot exceed partition_capacity ({item.partition_capacity}) of item '{item_id}'")
        return v

class PartitionUpdate(BaseModel):
    item_id: Optional[str] = None
    storage_section_id: Optional[str] = None
    rfid_tag_id: Optional[str] = None
    quantity: Optional[int] = None
    status: Optional[PartitionStatus] = None

    @field_validator('item_id')
    @classmethod
    def validate_item_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_validator('Item ID')(v)
        return v

    @field_validator('storage_section_id')
    @classmethod
    def validate_storage_section_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_validator('Storage Section ID')(v)
        return v

    @field_validator('rfid_tag_id')
    @classmethod
    def validate_rfid_tag_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_validator('RFID Tag ID')(v)
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: Optional[int], info) -> Optional[int]:
        if v is not None:
            v = bounded_int_optional_validator(0, 10000, 'Quantity')(v)
            item_id = info.data.get('item_id')
            if item_id:
                from app.models.item import Item
                from app.database import SessionLocal
                db = SessionLocal()
                item = db.query(Item).filter(Item.id == item_id).first()
                db.close()
                if not item:
                    raise ValueError(f"Item '{item_id}' not found for partition validation.")
                if item.partition_capacity is None:
                    raise ValueError(f"Item '{item_id}' does not have a partition_capacity set.")
                if v > item.partition_capacity:
                    raise ValueError(f"Quantity ({v}) cannot exceed partition_capacity ({item.partition_capacity}) of item '{item_id}'")
        return v

class PartitionResponse(PartitionBase):
    id: str

    class Config:
        from_attributes = True

class PaginatedPartitionsResponse(BaseModel):
    partitions: List[PartitionResponse]
    total_partitions: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, partitions: List[PartitionResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return cls(
            partitions=partitions,
            total_partitions=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
