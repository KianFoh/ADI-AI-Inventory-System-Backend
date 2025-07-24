from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.crud import user as user_crud
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(
    prefix="/users",
    tags=["users"]
)

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    # Fix: Use employeeid parameter
    if user_crud.get_user(db, employeeid=user.employeeId):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee ID already exists"
        )
    
    if user_crud.get_user_by_email(db, email=user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    if user_crud.get_user_by_name(db, name=user.name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Name already exists"
        )
    
    return user_crud.create_user(db=db, user=user)

@router.get("/", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all users with pagination"""
    return user_crud.get_users(db, skip=skip, limit=limit)

@router.get("/{employeeid}", response_model=UserResponse)
def get_user(employeeid: str, db: Session = Depends(get_db)):
    """Get user by employee ID"""
    # Already correct
    db_user = user_crud.get_user(db, employeeid=employeeid)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user

@router.put("/{employeeid}", response_model=UserResponse)
def update_user(employeeid: str, user: UserUpdate, db: Session = Depends(get_db)):
    """Update user by employee ID"""
    # Fix: Use employeeid parameter
    db_user = user_crud.update_user(db, employeeid=employeeid, user=user)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user

@router.delete("/{employeeid}", response_model=UserResponse)
def delete_user(employeeid: str, db: Session = Depends(get_db)):
    """Delete user by employee ID"""
    # Fix: Use employeeid parameter
    db_user = user_crud.delete_user(db, employeeid=employeeid)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return db_user