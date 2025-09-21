from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from math import ceil
import re
from app.models.item import ItemType, MeasureMethod
from app.validators import non_empty_string_preserve_case_validator, string_length_validator

class PartitionStatResponse(BaseModel):
    total_quantity: Optional[int] = None
    total_capacity: Optional[int] = None
    partition_capacity: Optional[int] = None
    high_threshold: Optional[float] = None
    low_threshold: Optional[float] = None
    stock_status: Optional[str] = None

    model_config = {"extra": "ignore", "exclude_none": True}

class LargeItemStatResponse(BaseModel):
    total_quantity: Optional[int] = None
    high_threshold: Optional[int] = None
    low_threshold: Optional[int] = None
    stock_status: Optional[str] = None

    model_config = {"extra": "ignore", "exclude_none": True}

class ContainerStatResponse(BaseModel):
    container_item_weight: Optional[float] = None
    container_weight: Optional[float] = None
    total_weight: Optional[float] = None
    high_threshold: Optional[float] = None
    low_threshold: Optional[float] = None
    stock_status: Optional[str] = None

    model_config = {"extra": "ignore", "exclude_none": True}

class ItemBase(BaseModel):
    id: str
    name: str
    manufacturer: str
    item_type: ItemType
    measure_method: Optional[MeasureMethod] = None
    image_url: Optional[str] = None

    # New shared metadata fields (present on DB & responses)
    process: Optional[str] = None
    tooling_used: Optional[str] = None
    vendor_pn: Optional[str] = None
    sap_pn: Optional[str] = None
    package_used: Optional[str] = None

class ItemCreate(BaseModel):
    id: Optional[str] = None
    name: str
    manufacturer: Optional[str] = None
    item_type: str
    measure_method: Optional[str] = None
    image: Optional[str] = None

    # inputs forwarded to per-type stat rows
    partition_capacity: Optional[int] = None

    # thresholds for partition (percent 0-100) - required for partition items
    partition_high: Optional[float] = None
    partition_low: Optional[float] = None

    # thresholds for large item (integers) - required for large_item
    large_high: Optional[int] = None
    large_low: Optional[int] = None

    # thresholds for container (floats) - required for container items
    container_high: Optional[float] = None
    container_low: Optional[float] = None
    container_item_weight: Optional[float] = None
    container_weight: Optional[float] = None
    # NOTE: clients MUST NOT provide total_weight/total_quantity — backend controls totals

    # New request fields
    process: Optional[str] = None
    tooling_used: Optional[str] = None
    vendor_pn: Optional[str] = None
    sap_pn: Optional[str] = None
    package_used: Optional[str] = None

    model_config = {
        "extra": "ignore",
        "str_strip_whitespace": True,
        "anystr_lower": False,
        "exclude_none": True
    }

    @field_validator("process")
    @classmethod
    def validate_process(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", v):
            raise ValueError("process must contain only uppercase letters and digits, no spaces")
        return v

    # validate partition thresholds (percent)
    @field_validator("partition_high", "partition_low")
    @classmethod
    def _validate_partition_thresholds(cls, v):
        if v is None:
            return v
        if not (0 <= v <= 100):
            raise ValueError("partition thresholds must be between 0 and 100")
        return v

    # validate container thresholds (non-negative)
    @field_validator("container_high", "container_low")
    @classmethod
    def _validate_container_thresholds(cls, v):
        if v is None:
            return v
        if v < 0:
            raise ValueError("container thresholds must be non-negative")
        return v

    # validate large thresholds (integers, non-negative)
    @field_validator("large_high", "large_low")
    @classmethod
    def _validate_large_thresholds(cls, v):
        if v is None:
            return v
        if v < 0:
            raise ValueError("large thresholds must be non-negative integers")
        return v

    @model_validator(mode="after")
    def _validate_threshold_order(self):
        # partition thresholds
        if self.partition_high is not None and self.partition_low is not None:
            if not (self.partition_high > self.partition_low):
                raise ValueError("partition_high must be greater than partition_low")
        # large item thresholds
        if self.large_high is not None and self.large_low is not None:
            if not (self.large_high > self.large_low):
                raise ValueError("large_high must be greater than large_low")
        # container thresholds
        if self.container_high is not None and self.container_low is not None:
            if not (self.container_high > self.container_low):
                raise ValueError("container_high must be greater than container_low")
        return self

    @model_validator(mode="after")
    def _validate_required_thresholds(self):
        t = (self.item_type or "").strip()
        if not t:
            raise ValueError("item_type is required")
        if t == "partition":
            if self.partition_high is None or self.partition_low is None:
                raise ValueError("partition_high and partition_low are required for partition items")
        elif t == "large_item":
            if self.large_high is None or self.large_low is None:
                raise ValueError("large_high and large_low are required for large_item items")
        elif t == "container":
            if self.container_high is None or self.container_low is None:
                raise ValueError("container_high and container_low are required for container items")
        return self

class ItemUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    item_type: Optional[str] = None
    measure_method: Optional[str] = None
    image: Optional[str] = None

    # optional stat inputs clients can change
    partition_capacity: Optional[int] = None
    # optional stat inputs - if client supplies a high or low, require the pair
    partition_high: Optional[float] = None
    partition_low: Optional[float] = None
    # NOTE: partition total_capacity/total_quantity are not accepted from client

    large_high: Optional[int] = None
    large_low: Optional[int] = None

    container_item_weight: Optional[float] = None
    container_weight: Optional[float] = None
    container_high: Optional[float] = None
    container_low: Optional[float] = None
    # NOTE: container total_weight/total_quantity are not accepted from client

    process: Optional[str] = None
    tooling_used: Optional[str] = None
    vendor_pn: Optional[str] = None
    sap_pn: Optional[str] = None
    package_used: Optional[str] = None

    model_config = {
        "extra": "ignore",
        "str_strip_whitespace": True,
        "anystr_lower": False,
        "exclude_none": True
    }

    @field_validator("process")
    @classmethod
    def validate_process_optional(cls, v):
        if v is None:
            return v
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", v):
            raise ValueError("process must contain only uppercase letters and digits, no spaces")
        return v

    # reuse same validators for thresholds
    @field_validator("partition_high", "partition_low", "container_high", "container_low")
    @classmethod
    def _validate_thresholds_optional(cls, v):
        if v is None:
            return v
        if isinstance(v, float) and v < 0:
            raise ValueError("threshold values must be non-negative")
        return v

    @field_validator("large_high", "large_low")
    @classmethod
    def _validate_large_thresholds_optional(cls, v):
        if v is None:
            return v
        if v < 0:
            raise ValueError("large thresholds must be non-negative integers")
        return v

    @model_validator(mode="after")
    def _validate_threshold_order_optional(self):
        # only validate when both values are provided
        if self.partition_high is not None and self.partition_low is not None:
            if not (self.partition_high > self.partition_low):
                raise ValueError("partition_high must be greater than partition_low")
        if self.large_high is not None and self.large_low is not None:
            if not (self.large_high > self.large_low):
                raise ValueError("large_high must be greater than large_low")
        if self.container_high is not None and self.container_low is not None:
            if not (self.container_high > self.container_low):
                raise ValueError("container_high must be greater than container_low")
        return self

    @model_validator(mode="after")
    def _validate_threshold_pairs_optional(self):
        # if client provides one side of a pair, require the other side too
        if (self.partition_high is None) ^ (self.partition_low is None):
            raise ValueError("both partition_high and partition_low must be provided together")
        if (self.large_high is None) ^ (self.large_low is None):
            raise ValueError("both large_high and large_low must be provided together")
        if (self.container_high is None) ^ (self.container_low is None):
            raise ValueError("both container_high and container_low must be provided together")
        return self

class ItemResponse(ItemBase):
    # per-type stat nested responses
    partition_stat: Optional[PartitionStatResponse] = None
    largeitem_stat: Optional[LargeItemStatResponse] = None
    container_stat: Optional[ContainerStatResponse] = None

    class Config:
        from_attributes = True

    @model_validator(mode='after')
    def fix_weights_for_non_container(self):
        if self.item_type != ItemType.CONTAINER:
            # ensure response doesn't include container weights for non-container types
            self.container_stat = None if getattr(self, "container_stat", None) is None else self.container_stat
        return self

class ItemStatsResponse(ItemResponse):
    total_quantity: Optional[int] = None
    total_capacity: Optional[int] = None
    total_weight: Optional[float] = None
    # counts for how many instances of each type are registered under the item
    partition_count: Optional[int] = None
    container_count: Optional[int] = None

    # Pydantic v2 config: ignore extra keys and exclude None fields from output
    model_config = {
        "extra": "ignore",
        "exclude_none": True
    }

class PaginatedItemsResponse(BaseModel):
    items: List[ItemStatsResponse]   # ensure items use ItemStatsResponse so extra fields are preserved
    total_items: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, items, total_count, page, page_size):
        total_pages = ceil(total_count / page_size) if page_size else 1
        return cls(
            items=items,
            total_items=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )
