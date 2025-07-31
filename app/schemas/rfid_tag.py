from pydantic import BaseModel
from typing import Optional

class RFIDTagBase(BaseModel):
    id: str
    assigned: bool = False

class RFIDTagCreate(RFIDTagBase):
    pass

class RFIDTagUpdate(BaseModel):
    assigned: Optional[bool] = None

class RFIDTagResponse(RFIDTagBase):
    class Config:
        from_attributes = True