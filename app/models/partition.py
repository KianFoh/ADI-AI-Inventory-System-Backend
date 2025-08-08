from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum

class PartitionStatus(enum.Enum):
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"

class Partition(Base):
    __tablename__ = "partitions"

    id = Column(String(255), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(255), ForeignKey("items.id"), nullable=False, index=True)
    storage_section_id = Column(String(255), ForeignKey("storage_sections.id"), nullable=False, index=True)
    rfid_tag_id = Column(String(255), ForeignKey("rfid_tags.id"), nullable=False, index=True)
    
    quantity = Column(Integer, nullable=False, default=0)
    capacity = Column(Integer, nullable=False)
    status = Column(Enum(PartitionStatus), nullable=False, default=PartitionStatus.AVAILABLE, index=True)
    
    item = relationship("Item", back_populates="partitions")
    storage_section = relationship("StorageSection", back_populates="partitions")
    rfid_tag = relationship("RFIDTag", back_populates="partition")
    
    def __repr__(self):
        return f"<Partition(id='{self.id}', quantity={self.quantity}/{self.capacity}, status='{self.status.value}')>"