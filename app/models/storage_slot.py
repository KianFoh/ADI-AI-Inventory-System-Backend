from sqlalchemy import Column, String, Boolean
from app.database import Base

class StorageSlot(Base):
    __tablename__ = "storage_slots"

    id = Column(String(255), primary_key=True, index=True)
    assigned = Column(Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<StorageSlot(id='{self.id}', occupied={self.occupied})>"