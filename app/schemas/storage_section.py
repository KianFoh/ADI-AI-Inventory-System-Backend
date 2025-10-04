from pydantic import BaseModel, field_validator, computed_field
from typing import Optional, List
import math
from app.models.storage_section import SectionColor
from app.validators import (
    storage_format_validator, 
    storage_format_optional_validator
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
    in_use: bool

    @classmethod
    def model_validate(cls, obj):
        # Compute in_use by checking references
        db = getattr(obj, '_sa_instance_state', None)
        # If obj is an ORM instance, check relationships
        in_use = False
        if hasattr(obj, 'containers') and obj.containers:
            in_use = True
        elif hasattr(obj, 'partitions') and obj.partitions:
            in_use = True
        elif hasattr(obj, 'large_items') and obj.large_items:
            in_use = True
        return super().model_validate({**obj.__dict__, 'in_use': in_use})

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