from sqlalchemy import Column, String, Integer, Enum, Float
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class ItemType(enum.Enum):
    PARTITION = "partition"
    LARGE_ITEM = "large_item"

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
    item_weight = Column(Float, nullable=True)
    partition_weight = Column(Float, nullable=True)
    unit = Column(Integer, nullable=False)
    image_path = Column(String(500), nullable=True)
    
    partitions = relationship("Partition", back_populates="item")
    large_items = relationship("LargeItem", back_populates="item")
    
    def __repr__(self):
        return f"<Item(id='{self.id}', name='{self.name}', type='{self.item_type.value}', unit={self.unit})>"
    
    @classmethod
    def get_available_item_types(cls):
        return [item_type.value for item_type in ItemType]
    
    @classmethod
    def get_available_measure_methods(cls):
        return [method.value for method in MeasureMethod]