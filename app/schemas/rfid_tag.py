from pydantic import BaseModel, field_validator
from typing import List
import math
from app.validators import non_empty_string_validator, boolean_validator

class RFIDTagBase(BaseModel):
    id: str
    assigned: bool = False

class RFIDTagCreate(BaseModel):
    id: str

    @field_validator('id')
    @classmethod
    def validate_tag_id(cls, v: str) -> str:
        return non_empty_string_validator("Tag ID")(v)

class RFIDTagUpdate(BaseModel):
    assigned: bool 

    @field_validator('assigned')
    @classmethod
    def validate_assigned(cls, v: bool) -> bool:
        return boolean_validator("Assigned")(v)

class RFIDTagResponse(RFIDTagBase):
    class Config:
        from_attributes = True

class PaginatedRFIDTagsResponse(BaseModel):
    tags: List[RFIDTagResponse]
    total_tags: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, tags: List[RFIDTagResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return cls(
            tags=tags,
            total_tags=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )