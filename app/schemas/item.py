from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from math import ceil
import re
from app.models.item import ItemType, MeasureMethod


# -----------------------------
# Shared Stat Response Schemas
# -----------------------------
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
    total_quantity: Optional[int] = None
    high_threshold: Optional[float] = None
    low_threshold: Optional[float] = None
    stock_status: Optional[str] = None

    model_config = {"extra": "ignore", "exclude_none": True}


# -----------------------------
# Item Base
# -----------------------------
class ItemBase(BaseModel):
    id: str
    name: str
    manufacturer: Optional[str] = None
    item_type: ItemType
    measure_method: Optional[MeasureMethod] = None
    image_url: Optional[str] = None

    # Metadata
    process: Optional[str] = None
    tooling_used: Optional[str] = None
    vendor_pn: Optional[str] = None
    sap_pn: Optional[str] = None
    package_used: Optional[str] = None


# -----------------------------
# Item Create
# -----------------------------
class ItemCreate(BaseModel):
    id: Optional[str] = None
    name: str
    manufacturer: Optional[str] = None
    item_type: str
    measure_method: Optional[MeasureMethod] = None
    image: str

    # Partition thresholds
    partition_capacity: Optional[int] = None
    partition_high: Optional[float] = None
    partition_low: Optional[float] = None

    # Large thresholds
    large_high: Optional[int] = None
    large_low: Optional[int] = None

    # Container thresholds
    container_high: Optional[float] = None
    container_low: Optional[float] = None
    container_item_weight: Optional[float] = None
    container_weight: Optional[float] = None

    # Metadata
    process: str
    tooling_used: Optional[str] = None
    vendor_pn: Optional[str] = None
    sap_pn: Optional[str] = None
    package_used: Optional[str] = None

    model_config = {"extra": "ignore", "str_strip_whitespace": True, "exclude_none": True}

    # ------------------- Validators -------------------
    @field_validator("process")
    def validate_process(cls, v):
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", v):
            raise ValueError("process must contain only uppercase letters and digits, no spaces")
        return v

    @field_validator("partition_high", "partition_low")
    def validate_partition_thresholds(cls, v):
        if v is not None and not (0 <= v <= 100):
            raise ValueError("partition thresholds must be between 0 and 100")
        return v

    @field_validator("container_high", "container_low")
    def validate_container_thresholds(cls, v):
        if v is not None and v < 0:
            raise ValueError("container thresholds must be non-negative")
        return v

    @field_validator("large_high", "large_low")
    def validate_large_thresholds(cls, v):
        if v is not None and v < 0:
            raise ValueError("large thresholds must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_threshold_order(self):
        def check(high, low, label):
            if high is not None and low is not None and high <= low:
                raise ValueError(f"{label}_high must be greater than {label}_low")

        check(self.partition_high, self.partition_low, "partition")
        check(self.large_high, self.large_low, "large")
        check(self.container_high, self.container_low, "container")
        return self

    @model_validator(mode="after")
    def validate_required_thresholds(self):
        t = (self.item_type or "").strip()
        if not t:
            raise ValueError("item_type is required")

        required = {
            "partition": ("partition_high", "partition_low"),
            "large_item": ("large_high", "large_low"),
            "container": ("container_high", "container_low"),
        }

        if t in required:
            fields = required[t]
            if any(getattr(self, f) is None for f in fields):
                raise ValueError(f"{fields[0]} and {fields[1]} are required for {t} items")
        return self

    # Ensure measure_method matches item_type
    @model_validator(mode="after")
    def set_measure_method_from_type(self):
        t = (self.item_type or "").strip()
        if t == "partition":
            self.measure_method = MeasureMethod.VISION
        elif t == "container":
            self.measure_method = MeasureMethod.WEIGHT
        elif t == "large_item":
            self.measure_method = None
        return self


# -----------------------------
# Item Update
# -----------------------------
class ItemUpdate(BaseModel):
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    item_type: Optional[str] = None
    measure_method: Optional[MeasureMethod] = None
    image: Optional[str] = None

    # Partition thresholds
    partition_capacity: Optional[int] = None
    partition_high: Optional[float] = None
    partition_low: Optional[float] = None

    # Large thresholds
    large_high: Optional[int] = None
    large_low: Optional[int] = None

    # Container thresholds
    container_item_weight: Optional[float] = None
    container_weight: Optional[float] = None
    container_high: Optional[float] = None
    container_low: Optional[float] = None

    # Metadata
    process: Optional[str] = None
    tooling_used: Optional[str] = None
    vendor_pn: Optional[str] = None
    sap_pn: Optional[str] = None
    package_used: Optional[str] = None

    model_config = {"extra": "ignore", "str_strip_whitespace": True, "exclude_none": True}

    # ------------------- Validators -------------------
    @field_validator("process")
    def validate_process_optional(cls, v):
        if v is not None:
            v = v.strip().upper()
            if not re.fullmatch(r"[A-Z0-9]+", v):
                raise ValueError("process must contain only uppercase letters and digits, no spaces")
        return v

    @field_validator("partition_high", "partition_low", "container_high", "container_low")
    def validate_thresholds_optional(cls, v):
        if isinstance(v, float) and v < 0:
            raise ValueError("threshold values must be non-negative")
        return v

    @field_validator("large_high", "large_low")
    def validate_large_thresholds_optional(cls, v):
        if v is not None and v < 0:
            raise ValueError("large thresholds must be non-negative")
        return v

    @model_validator(mode="after")
    def validate_threshold_order_optional(self):
        def check(high, low, label):
            if high is not None and low is not None and high <= low:
                raise ValueError(f"{label}_high must be greater than {label}_low")

        check(self.partition_high, self.partition_low, "partition")
        check(self.large_high, self.large_low, "large")
        check(self.container_high, self.container_low, "container")
        return self

    @model_validator(mode="after")
    def validate_threshold_pairs_optional(self):
        def require_both(a, b, label):
            if (a is None) ^ (b is None):
                raise ValueError(f"both {label}_high and {label}_low must be provided together")

        require_both(self.partition_high, self.partition_low, "partition")
        require_both(self.large_high, self.large_low, "large")
        require_both(self.container_high, self.container_low, "container")
        return self

    # If item_type is updated, enforce corresponding measure_method
    @model_validator(mode="after")
    def set_measure_method_from_type_optional(self):
        if not self.item_type:
            return self
        t = self.item_type.strip()
        if t == "partition":
            self.measure_method = MeasureMethod.VISION
        elif t == "container":
            self.measure_method = MeasureMethod.WEIGHT
        elif t == "large_item":
            self.measure_method = None
        return self


# -----------------------------
# Item Response
# -----------------------------
class ItemResponse(ItemBase):
    partition_stat: Optional[PartitionStatResponse] = None
    largeitem_stat: Optional[LargeItemStatResponse] = None
    container_stat: Optional[ContainerStatResponse] = None

    model_config = {"from_attributes": True}

class ItemStatsResponse(ItemResponse):
    total_quantity: Optional[int] = None
    total_capacity: Optional[int] = None
    total_weight: Optional[float] = None
    partition_count: Optional[int] = None
    container_count: Optional[int] = None

    model_config = {"extra": "ignore", "exclude_none": True}


# -----------------------------
# Paginated Items
# -----------------------------
class PaginatedItemsResponse(BaseModel):
    items: List[ItemStatsResponse]
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
            has_previous=page > 1,
        )
