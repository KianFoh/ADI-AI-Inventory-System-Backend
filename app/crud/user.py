from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import List, Optional

def get_user(db: Session, employeeid: str) -> Optional[User]:
    return db.query(User).filter(User.employeeId == employeeid).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_name(db: Session, name: str) -> Optional[User]:
    return db.query(User).filter(User.name == name).first()

def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate) -> User:
    # Fix: Use model_dump() instead of dict()
    db_user = User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, employeeid: str, user: UserUpdate) -> Optional[User]:
    db_user = db.query(User).filter(User.employeeId == employeeid).first()
    if db_user:
        # Fix: Use model_dump() instead of dict()
        update_data = user.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, employeeid: str) -> Optional[User]:
    db_user = db.query(User).filter(User.employeeId == employeeid).first()
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user