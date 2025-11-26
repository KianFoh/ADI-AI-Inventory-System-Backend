from sqlalchemy import Column, String, ForeignKey, Enum, event, text
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class LargeItemStatus(enum.Enum):
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"

class LargeItem(Base):
    __tablename__ = "large_items"

    id = Column(String(20), primary_key=True, index=True)
    item_id = Column(String(255), ForeignKey("items.id"), nullable=False, index=True)
    storage_section_id = Column(String(255), ForeignKey("storage_sections.id"), nullable=False, index=True)
    rfid_tag_id = Column(String(255), ForeignKey("rfid_tags.id"), nullable=False, index=True)
    status = Column(Enum(LargeItemStatus), nullable=False, default=LargeItemStatus.AVAILABLE, index=True)
    
    item = relationship("Item", back_populates="large_items")
    storage_section = relationship("StorageSection", back_populates="large_items")
    rfid_tag = relationship("RFIDTag", back_populates="large_item")
    
    def __repr__(self):
        return f"<LargeItem(id='{self.id}', item_id='{self.item_id}', status='{self.status.value}')>"

# Event listener to generate sequential LargeItem IDs (sequence-backed, atomic)
@event.listens_for(LargeItem, "before_insert")
def generate_largeitem_id(mapper, connection, target):
    prefix = "L"
    seq_name = "large_items_seq"

    # create sequence if it doesn't exist (prefer to provision via migration in production)
    try:
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))
    except Exception:
        pass

    # atomically get the next value
    next_val = connection.execute(text(f"SELECT nextval('{seq_name}')")).scalar()
    target.id = f"{prefix}{int(next_val)}"
