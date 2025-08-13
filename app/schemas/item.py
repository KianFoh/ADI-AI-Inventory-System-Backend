from pydantic import BaseModel, field_validator, computed_field, model_validator
from typing import Optional, List
import math
from app.models.item import ItemType, MeasureMethod
from app.validators import (
    string_length_validator,
    non_empty_string_preserve_case_validator,
    bounded_int_validator,
    bounded_int_optional_validator
)

class ItemBase(BaseModel):
    id: str
    name: str
    manufacturer: str
    item_type: ItemType
    measure_method: Optional[MeasureMethod] = None
    unit: int
    image_url: Optional[str] = None

class ItemCreate(BaseModel):
    id: str
    name: str
    manufacturer: str
    item_type: ItemType
    unit: int
    image: Optional[str] = None
    measure_method: Optional[MeasureMethod] = None

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: str) -> str:
        return string_length_validator(255, 'Item ID')(v)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return non_empty_string_preserve_case_validator('Item name')(v)

    @field_validator('manufacturer')
    @classmethod
    def validate_manufacturer(cls, v: str) -> str:
        return non_empty_string_preserve_case_validator('Manufacturer')(v)

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: int) -> int:
        return bounded_int_validator(1, 100, 'Unit')(v)

    @model_validator(mode='after')
    def set_measure_method_based_on_type(self):
        """Auto-assign measure_method based on item_type"""
        if self.item_type == ItemType.PARTITION:
            self.measure_method = MeasureMethod.VISION
        elif self.item_type == ItemType.LARGE_ITEM:
            self.measure_method = None
        elif self.item_type == ItemType.CONTAINER:
            self.measure_method = MeasureMethod.WEIGHT
        
        return self

class ItemUpdate(BaseModel):
    id: Optional[str] = None  # Added ID field for updates
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    item_type: Optional[ItemType] = None  # Added item_type for updates
    unit: Optional[int] = None
    image: Optional[str] = None
    measure_method: Optional[MeasureMethod] = None  # Added for consistency

    @field_validator('id')
    @classmethod
    def validate_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return string_length_validator(255, 'Item ID')(v)
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_preserve_case_validator('Item name')(v)
        return v

    @field_validator('manufacturer')
    @classmethod
    def validate_manufacturer(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_preserve_case_validator('Manufacturer')(v)
        return v

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: Optional[int]) -> Optional[int]:
        return bounded_int_optional_validator(1, 100, 'Unit')(v)

    @model_validator(mode='after')
    def set_measure_method_based_on_type(self):
        """Auto-assign measure_method based on item_type if item_type is being updated"""
        if self.item_type is not None:
            if self.item_type == ItemType.PARTITION:
                self.measure_method = MeasureMethod.VISION
            elif self.item_type == ItemType.LARGE_ITEM:
                self.measure_method = None
            elif self.item_type == ItemType.CONTAINER:
                self.measure_method = MeasureMethod.WEIGHT
        
        return self

class ItemResponse(ItemBase):
    class Config:
        from_attributes = True

class ItemStatsResponse(ItemResponse):
    partition_count: int = 0
    large_item_count: int = 0
    container_count: int = 0
    total_instances: int = 0
    
    @computed_field
    @property
    def has_instances(self) -> bool:
        return self.total_instances > 0
    
    @computed_field
    @property
    def instance_distribution(self) -> dict:
        return {
            "partitions": self.partition_count,
            "large_items": self.large_item_count,
            "containers": self.container_count
        }

class PaginatedItemsResponse(BaseModel):
    items: List[ItemResponse]
    total_items: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, items: List[ItemResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return cls(
            items=items,
            total_items=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )