from pydantic import BaseModel, field_validator
from typing import Optional, List
import math
from app.models.container import ContainerStatus

class ContainerBase(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str
    weight: float
    container_weight: float
    status: ContainerStatus = ContainerStatus.AVAILABLE

class ContainerCreate(BaseModel):
    item_id: str
    storage_section_id: str
    rfid_tag_id: str
    weight: float = 0.0
    container_weight: float

    @field_validator('weight')
    @classmethod
    def validate_weight(cls, v: float) -> float:
        if v < 0:
            raise ValueError('Weight cannot be negative')
        return v

    @field_validator('container_weight')
    @classmethod
    def validate_container_weight(cls, v: float) -> float:
        if v < 0:
            raise ValueError('Container weight cannot be negative')
        return v

class ContainerUpdate(BaseModel):
    item_id: Optional[str] = None
    storage_section_id: Optional[str] = None
    rfid_tag_id: Optional[str] = None
    weight: Optional[float] = None
    container_weight: Optional[float] = None
    status: Optional[ContainerStatus] = None

    @field_validator('weight')
    @classmethod
    def validate_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError('Weight cannot be negative')
        return v

    @field_validator('container_weight')
    @classmethod
    def validate_container_weight(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError('Container weight cannot be negative')
        return v

class ContainerResponse(ContainerBase):
    id: str

    class Config:
        from_attributes = True

class PaginatedContainersResponse(BaseModel):
    containers: List[ContainerResponse]
    total_containers: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, containers: List[ContainerResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        return cls(
            containers=containers,
            total_containers=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )