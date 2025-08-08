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
    quantity: int = 0
    capacity: int
    status: PartitionStatus = PartitionStatus.AVAILABLE

class PartitionCreate(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str
    capacity: int

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

    @field_validator('capacity')
    @classmethod
    def validate_capacity(cls, v: int) -> int:
        return bounded_int_validator(1, 10000, 'Capacity')(v)

class PartitionUpdate(BaseModel):
    storage_section_id: Optional[str] = None
    quantity: Optional[int] = None
    capacity: Optional[int] = None
    status: Optional[PartitionStatus] = None

    @field_validator('storage_section_id')
    @classmethod
    def validate_storage_section_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_validator('Storage Section ID')(v)
        return v

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: Optional[int]) -> Optional[int]:
        return bounded_int_optional_validator(0, 10000, 'Quantity')(v)

    @field_validator('capacity')
    @classmethod
    def validate_capacity(cls, v: Optional[int]) -> Optional[int]:
        return bounded_int_optional_validator(1, 10000, 'Capacity')(v)

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