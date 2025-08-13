from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from app.database import Base
import uuid
import enum

class ContainerStatus(enum.Enum):
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"

class Container(Base):
    __tablename__ = "containers"

    id = Column(String(255), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    item_id = Column(String(255), ForeignKey("items.id"), nullable=False, index=True)
    storage_section_id = Column(String(255), ForeignKey("storage_sections.id"), nullable=False, index=True)
    rfid_tag_id = Column(String(255), ForeignKey("rfid_tags.id"), nullable=False, index=True)
    
    # Weight of items in the container
    weight = Column(Float, nullable=False, default=0.0)
    # Weight of the container
    container_weight = Column(Float, nullable=False, default=0.0)
    status = Column(Enum(ContainerStatus), nullable=False, default=ContainerStatus.AVAILABLE, index=True)
    
    item = relationship("Item", back_populates="containers")
    storage_section = relationship("StorageSection", back_populates="containers")
    rfid_tag = relationship("RFIDTag", back_populates="container")
    
    @property
    def total_weight(self):
        """Total weight including container and items"""
        return self.weight + self.container_weight

    def __repr__(self):
        return f"<Container(id='{self.id}', weight={self.weight}kg, container_weight={self.container_weight}kg, total={self.total_weight}kg, status='{self.status.value}')>"