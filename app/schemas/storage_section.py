from pydantic import BaseModel, field_validator, computed_field
from typing import Optional, List
import math
from app.models.storage_section import SectionColor
from app.validators import (
    storage_format_validator, 
    storage_format_optional_validator,
    bounded_int_validator,
    bounded_int_optional_validator
)

class StorageSectionBase(BaseModel):
    floor: str
    cabinet: str
    layer: str
    color: SectionColor

class StorageSectionCreate(BaseModel):
    floor: str
    cabinet: str
    layer: str
    color: SectionColor

    @field_validator('floor')
    @classmethod
    def validate_floor(cls, v: str) -> str:
        return storage_format_validator('F', 'Floor')(v)

    @field_validator('cabinet')
    @classmethod
    def validate_cabinet(cls, v: str) -> str:
        return storage_format_validator('C', 'Cabinet')(v)

    @field_validator('layer')
    @classmethod
    def validate_layer(cls, v: str) -> str:
        return storage_format_validator('L', 'Layer')(v)


class StorageSectionUpdate(BaseModel):
    floor: Optional[str] = None
    cabinet: Optional[str] = None
    layer: Optional[str] = None
    color: Optional[SectionColor] = None

    @field_validator('floor')
    @classmethod
    def validate_floor(cls, v: Optional[str]) -> Optional[str]:
        return storage_format_optional_validator('F', 'Floor')(v)

    @field_validator('cabinet')
    @classmethod
    def validate_cabinet(cls, v: Optional[str]) -> Optional[str]:
        return storage_format_optional_validator('C', 'Cabinet')(v)

    @field_validator('layer')
    @classmethod
    def validate_layer(cls, v: Optional[str]) -> Optional[str]:
        return storage_format_optional_validator('L', 'Layer')(v)

class StorageSectionResponse(StorageSectionBase):
    id: str
    class Config:
        from_attributes = True

class PaginatedStorageSectionsResponse(BaseModel):
    sections: List[StorageSectionResponse]
    total_sections: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, sections: List[StorageSectionResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return cls(
            sections=sections,
            total_sections=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )