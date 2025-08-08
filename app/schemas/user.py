from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List
import math
from app.validators import non_empty_string_validator

class UserBase(BaseModel):
    employeeId: str
    email: EmailStr
    name: str
    admin: bool = False

class UserCreate(UserBase):
    @field_validator('employeeId')
    @classmethod
    def validate_employee_id(cls, v: str) -> str:
        return non_empty_string_validator('Employee ID')(v)

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        return non_empty_string_validator('Name')(v)

class UserUpdate(BaseModel):
    employeeId: Optional[str] = None
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    admin: Optional[bool] = None

    @field_validator('employeeId')
    @classmethod
    def validate_employee_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_validator('Employee ID')(v)
        return v

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return non_empty_string_validator('Name')(v)
        return v

class UserResponse(UserBase):
    class Config:
        from_attributes = True

class PaginatedUsersResponse(BaseModel):
    users: List[UserResponse]
    total_users: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool

    @classmethod
    def create(cls, users: List[UserResponse], total_count: int, page: int, page_size: int):
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0
        
        return cls(
            users=users,
            total_users=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1
        )