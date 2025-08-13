from sqlalchemy import Column, Float, String, Integer, Enum, DateTime, ForeignKey
from app.database import Base
from datetime import datetime, timezone
import uuid
import enum

class TransactionType(enum.Enum):
    WITHDRAW = "withdraw"
    RETURN = "return"
    CONSUMED = "consumed"

class ItemType(enum.Enum):
    PARTITION = "partition"
    LARGE_ITEM = "large_item"
    CONTAINER = "container"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(255), primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    transaction_type = Column(Enum(TransactionType), nullable=False, index=True)
    transaction_date = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    item_type = Column(Enum(ItemType), nullable=False, index=True)
    item_id = Column(String(255), nullable=False, index=True)
    item_name = Column(String(255), nullable=False, index=True)
    
    partition_id = Column(String(255), nullable=True, index=True)   # If partition
    large_item_id = Column(String(255), nullable=True, index=True)  # If large item
    container_id = Column(String(255), nullable=True, index=True)   # If container
    storage_section_id = Column(String(255), nullable=False, index=True)
    
    # Partition
    previous_quantity = Column(Integer, nullable=True)
    current_quantity = Column(Integer, nullable=True)
    quantity_change = Column(Integer, nullable=True)  # +5, -3, etc.

    # Container
    previous_weight = Column(Float, nullable=True)
    current_weight = Column(Float, nullable=True)
    weight_change = Column(Float, nullable=True) 
    
    user_name = Column(String(255), nullable=True, index=True)
    
    def __repr__(self):
        return f"<Transaction(id='{self.id}', type='{self.transaction_type.value}', item='{self.item_name}')>"