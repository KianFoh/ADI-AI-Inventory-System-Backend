from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    employeeId = Column(String(255), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    admin = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<User(employeeId={self.employeeId}, email='{self.email}', name='{self.name}')>"