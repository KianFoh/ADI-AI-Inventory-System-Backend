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

# Event listener to generate sequential LargeItem IDs
@event.listens_for(LargeItem, "before_insert")
def generate_largeitem_id(mapper, connection, target):
    prefix = "L"

    # Query the max existing number
    result = connection.execute(
        text(f"SELECT id FROM large_items WHERE id LIKE '{prefix}%' ORDER BY id DESC LIMIT 1")
    ).fetchone()

    if result is None:
        next_number = 1
    else:
        last_id = result[0]
        last_number = int(last_id[1:])
        next_number = last_number + 1

    target.id = f"{prefix}{next_number}"
