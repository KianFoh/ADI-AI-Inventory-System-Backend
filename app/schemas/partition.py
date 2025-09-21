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

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v, info):
        """
        Validate quantity against the configured partition capacity.
        Support cases where the incoming 'item' may be an ORM Item (with
        .partition_stat.partition_capacity) or older Item with .partition_capacity.
        If capacity can't be determined, do not raise here (backend will manage totals).
        """
        # Try to locate the related item object from validator context/data
        item = None
        try:
            item = info.data.get("item") if getattr(info, "data", None) else None
        except Exception:
            item = None

        # Safely read partition_capacity from item.partition_stat or fallback to item.partition_capacity
        partition_capacity = None
        if item is not None:
            partition_capacity = getattr(getattr(item, "partition_stat", None), "partition_capacity", None)
            if partition_capacity is None:
                partition_capacity = getattr(item, "partition_capacity", None)

        # If capacity is known, enforce the check
        if partition_capacity is not None:
            try:
                cap = int(partition_capacity)
                if v > cap:
                    raise ValueError(f"quantity ({v}) exceeds partition_capacity ({cap})")
            except ValueError:
                # re-raise capacity validation errors
                raise
            except Exception:
                # ignore conversion errors and allow backend to handle
                pass

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
