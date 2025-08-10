from pydantic import BaseModel, field_validator, computed_field
from typing import Optional, List
import math
from app.models.item import ItemType, MeasureMethod
from app.validators import (
    string_length_validator,
    non_empty_string_preserve_case_validator,
    bounded_int_validator,
    bounded_int_optional_validator,
    positive_float_optional_validator
)

class ItemBase(BaseModel):
    id: str
    name: str
    manufacturer: str
    item_type: ItemType
    measure_method: Optional[MeasureMethod] = None
    item_weight: Optional[float] = None
    partition_weight: Optional[float] = None
    unit: int
    image_url: Optional[str] = None

class ItemCreate(BaseModel):
    id: str
    name: str
    manufacturer: str
    item_type: ItemType
    measure_method: Optional[MeasureMethod] = None
    item_weight: Optional[float] = None
    partition_weight: Optional[float] = None
    unit: int
    image: Optional[str] = None

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

    @field_validator('measure_method')
    @classmethod
    def validate_measure_method(cls, v, values):
        item_type = values.data.get('item_type') if hasattr(values, 'data') else None
        
        if item_type == ItemType.PARTITION and v is None:
            raise ValueError('Measure method is required for partition items')
        if item_type == ItemType.LARGE_ITEM and v is not None:
            raise ValueError('Measure method should be null for large items')
        return v

    @field_validator('item_weight')
    @classmethod
    def validate_item_weight(cls, v, values):
        measure_method = values.data.get('measure_method') if hasattr(values, 'data') else None
        
        if measure_method == MeasureMethod.WEIGHT and v is None:
            raise ValueError('Item weight is required for weight measure method')
        if measure_method == MeasureMethod.VISION and v is not None:
            raise ValueError('Item weight should be null for vision measure method')
        if v is not None and v <= 0:
            raise ValueError('Item weight must be positive')
        return v

    @field_validator('partition_weight')
    @classmethod
    def validate_partition_weight(cls, v: Optional[float]) -> Optional[float]:
        return positive_float_optional_validator('Partition weight')(v)

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    measure_method: Optional[MeasureMethod] = None
    item_weight: Optional[float] = None
    partition_weight: Optional[float] = None
    unit: Optional[int] = None
    image: Optional[str] = None

    @field_validator('unit')
    @classmethod
    def validate_unit(cls, v: Optional[int]) -> Optional[int]:
        return bounded_int_optional_validator(1, 100, 'Unit')(v)

    @field_validator('item_weight')
    @classmethod
    def validate_item_weight(cls, v: Optional[float]) -> Optional[float]:
        return positive_float_optional_validator('Item weight')(v)

    @field_validator('partition_weight')
    @classmethod
    def validate_partition_weight(cls, v: Optional[float]) -> Optional[float]:
        return positive_float_optional_validator('Partition weight')(v)

class ItemResponse(ItemBase):
    class Config:
        from_attributes = True

class ItemStatsResponse(ItemResponse):
    partition_count: int = 0
    large_item_count: int = 0
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
            "large_items": self.large_item_count
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