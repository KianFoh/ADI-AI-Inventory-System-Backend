from pydantic import BaseModel, field_validator
from typing import Optional, List
import math
from app.models.large_item import LargeItemStatus
from app.validators import non_empty_string_validator

class LargeItemBase(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str
    status: LargeItemStatus = LargeItemStatus.AVAILABLE

class LargeItemCreate(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str

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

class LargeItemUpdate(BaseModel):
    item_id: Optional[str] = None
    storage_section_id: Optional[str] = None
    rfid_tag_id: Optional[str] = None
    status: Optional[LargeItemStatus] = None

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

class LargeItemResponse(LargeItemBase):
    id: str

    class Config:
        from_attributes = True

class PaginatedLargeItemsResponse(BaseModel):
    large_items: List[LargeItemResponse]
    total_large_items: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, large_items: List[LargeItemResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return cls(
            large_items=large_items,
            total_large_items=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )