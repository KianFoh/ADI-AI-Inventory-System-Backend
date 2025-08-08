from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import user as user_crud
from app.schemas.user import (
    UserCreate, 
    UserUpdate, 
    UserResponse,
    PaginatedUsersResponse
)

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.get("/", response_model=PaginatedUsersResponse)
def get_users(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search in employeeId, name, or email"),
    admin: Optional[bool] = Query(None, description="Filter by admin status (true/false)"),
    db: Session = Depends(get_db)
):
    """Get users with pagination and search"""
    users, total_count = user_crud.get_users(
        db, 
        page=page, 
        page_size=page_size, 
        search=search,
        admin_filter=admin
    )
    
    user_responses = [UserResponse.model_validate(user) for user in users]
    
    return PaginatedUsersResponse.create(
        users=user_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/search", response_model=List[UserResponse])
def search_users(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Quick search users for autocomplete/dropdown"""
    users = user_crud.search_users_by_keyword(db, keyword=q, limit=limit)
    return [UserResponse.model_validate(user) for user in users]

@router.get("/admins", response_model=List[UserResponse])
def get_admin_users(db: Session = Depends(get_db)):
    """Get all admin users"""
    users = user_crud.get_admin_users(db)
    return [UserResponse.model_validate(user) for user in users]

@router.get("/{employeeId}", response_model=UserResponse)
def get_user(employeeId: str, db: Session = Depends(get_db)):
    """Get user by employee ID"""
    user = user_crud.get_user(db, employeeid=employeeId)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(user)

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create new user"""
    if user_crud.get_user(db, employeeid=user.employeeId):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this employee ID already exists"
        )
    
    if user_crud.get_user_by_email(db, email=user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    
    created_user = user_crud.create_user(db=db, user=user)
    return UserResponse.model_validate(created_user)

@router.put("/{employeeId}", response_model=UserResponse)
def update_user(employeeId: str, user: UserUpdate, db: Session = Depends(get_db)):
    """Update user"""
    # Check if changing employeeId and new one already exists
    if user.employeeId and user.employeeId != employeeId:
        if user_crud.get_user(db, employeeid=user.employeeId):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this employee ID already exists"
            )
    
    # Check if changing email and new one already exists
    if user.email:
        existing_user = user_crud.get_user_by_email(db, email=user.email)
        if existing_user and existing_user.employeeId != employeeId:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
    
    updated_user = user_crud.update_user(db, employeeid=employeeId, user=user)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(updated_user)

@router.delete("/{employeeId}", response_model=UserResponse)
def delete_user(employeeId: str, db: Session = Depends(get_db)):
    """Delete user"""
    deleted_user = user_crud.delete_user(db, employeeid=employeeId)
    if not deleted_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(deleted_user)

@router.get("/count/total", response_model=int)
def get_user_count(db: Session = Depends(get_db)):
    return user_crud.get_user_count(db)

@router.get("/count/admins", response_model=int)
def get_admin_count(db: Session = Depends(get_db)):
    return user_crud.get_admin_count(db)