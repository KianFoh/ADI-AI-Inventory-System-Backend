from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from typing import List, Optional, Tuple

def get_user(db: Session, employeeid: str) -> Optional[User]:
    return db.query(User).filter(User.employeeId == employeeid).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()

def get_user_by_name(db: Session, name: str) -> Optional[User]:
    return db.query(User).filter(User.name == name).first()

def get_users(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    admin_filter: Optional[bool] = None
) -> Tuple[List[User], int]:
    """Get users with pagination and search"""
    query = db.query(User)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.employeeId.ilike(search_term),
                User.name.ilike(search_term),
                User.email.ilike(search_term)
            )
        )
    
    if admin_filter is not None:
        query = query.filter(User.admin == admin_filter)
    
    query = query.order_by(User.employeeId)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    users = query.offset(skip).limit(page_size).all()
    
    return users, total_count

def create_user(db: Session, user: UserCreate) -> User:
    db_user = User(**user.model_dump())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, employeeid: str, user: UserUpdate) -> Optional[User]:
    db_user = db.query(User).filter(User.employeeId == employeeid).first()
    if not db_user:
        return None
    
    update_data = user.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def delete_user(db: Session, employeeid: str) -> Optional[User]:
    db_user = db.query(User).filter(User.employeeId == employeeid).first()
    if not db_user:
        return None
    
    db.delete(db_user)
    db.commit()
    return db_user

def search_users_by_keyword(db: Session, keyword: str, limit: int = 20) -> List[User]:
    search_term = f"%{keyword}%"
    return db.query(User).filter(
        or_(
            User.employeeId.ilike(search_term),
            User.name.ilike(search_term),
            User.email.ilike(search_term)
        )
    ).order_by(User.name).limit(limit).all()

def get_admin_users(db: Session) -> List[User]:
    return db.query(User).filter(User.admin == True).order_by(User.name).all()

def get_regular_users(db: Session) -> List[User]:
    return db.query(User).filter(User.admin == False).order_by(User.name).all()

def get_user_count(db: Session) -> int:
    return db.query(User).count()

def get_admin_count(db: Session) -> int:
    return db.query(User).filter(User.admin == True).count()