from sqlalchemy import Column, String, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum

class LargeItemStatus(enum.Enum):
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"

class LargeItem(Base):
    __tablename__ = "large_items"

    id = Column(String(255), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(255), ForeignKey("items.id"), nullable=False, index=True)
    storage_section_id = Column(String(255), ForeignKey("storage_sections.id"), nullable=False, index=True)
    rfid_tag_id = Column(String(255), ForeignKey("rfid_tags.id"), nullable=False, index=True)
    status = Column(Enum(LargeItemStatus), nullable=False, default=LargeItemStatus.AVAILABLE, index=True)
    
    item = relationship("Item", back_populates="large_items")
    storage_section = relationship("StorageSection", back_populates="large_items")
    rfid_tag = relationship("RFIDTag", back_populates="large_item")
    
    def __repr__(self):
        return f"<LargeItem(id='{self.id}', item_id='{self.item_id}', status='{self.status.value}')>"