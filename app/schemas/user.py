from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    employeeId: str
    email: EmailStr
    name: str
    admin: bool = False

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    employeeId: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    admin: Optional[bool] = None

class UserResponse(UserBase):
    # Remove created_at and updated_at fields
    class Config:
        from_attributes = True