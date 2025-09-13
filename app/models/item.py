from sqlalchemy import Column, String, Integer, Enum, Float
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class ItemType(enum.Enum):
    PARTITION = "partition"
    LARGE_ITEM = "large_item"
    CONTAINER = "container"

class MeasureMethod(enum.Enum):
    VISION = "vision"
    WEIGHT = "weight"

class Item(Base):
    __tablename__ = "items"

    id = Column(String(255), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    manufacturer = Column(String(255), nullable=False, index=True)
    item_type = Column(Enum(ItemType), nullable=False)
    measure_method = Column(Enum(MeasureMethod), nullable=True)
    image_path = Column(String(500), nullable=True)

    # Container-specific attributes
    container_item_weight = Column(Float, nullable=True)
    container_weight = Column(Float, nullable=True)

    # Partition-specific attributes
    partition_capacity = Column(Integer, nullable=True)

    # New fields
    process = Column(String(50), nullable=False, index=True)   # uppercase letters/numbers, validated in schema
    tooling_used = Column(String(255), nullable=True)
    vendor_pn = Column(String(255), nullable=True)             # vendor part number
    sap_pn = Column(String(255), nullable=True)                # SAP part number
    package_used = Column(String(255), nullable=True)

    # Relationships
    partitions = relationship("Partition", back_populates="item")
    large_items = relationship("LargeItem", back_populates="item")
    containers = relationship("Container", back_populates="item")
    
    def __repr__(self):
        return f"<Item(id='{self.id}', name='{self.name}', type='{self.item_type.value}')>"
