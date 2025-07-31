from pydantic import BaseModel, field_validator
from typing import Optional
import re

class StorageSlotBase(BaseModel):
    id: str
    occupied: bool = False

    @field_validator('id')
    @classmethod
    def validate_slot_format(cls, v: str) -> str:
        pattern = r'^F\d+-S\d+-[A-Z]\d+$'
        if not re.match(pattern, v):
            raise ValueError('StorageSlot ID must be in format: F1-S1-A1 (Floor-Storage-Slot)')
        return v

class StorageSlotCreate(StorageSlotBase):
    pass

class StorageSlotUpdate(BaseModel):
    occupied: Optional[bool] = None

class StorageSlotResponse(StorageSlotBase):
    class Config:
        from_attributes = True