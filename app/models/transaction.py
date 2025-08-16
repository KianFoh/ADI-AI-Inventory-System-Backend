from sqlalchemy import Column, String, Integer, Enum, DateTime, event, Float, text
from app.database import Base
from datetime import datetime, timezone
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

    id = Column(String(20), primary_key=True, index=True)
    transaction_type = Column(Enum(TransactionType), nullable=False, index=True)
    transaction_date = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    item_type = Column(Enum(ItemType), nullable=False, index=True)
    item_id = Column(String(255), nullable=False, index=True)
    item_name = Column(String(255), nullable=False, index=True)
    
    partition_id = Column(String(20), nullable=True, index=True)
    large_item_id = Column(String(20), nullable=True, index=True)
    container_id = Column(String(20), nullable=True, index=True)
    storage_section_id = Column(String(255), nullable=False, index=True)

    previous_quantity = Column(Integer, nullable=True)
    current_quantity = Column(Integer, nullable=True)
    quantity_change = Column(Integer, nullable=True)

    previous_weight = Column(Float, nullable=True)
    current_weight = Column(Float, nullable=True)
    weight_change = Column(Float, nullable=True) 
    
    user_name = Column(String(255), nullable=True, index=True)
    
    def __repr__(self):
        return f"<Transaction(id='{self.id}', type='{self.transaction_type.value}', item='{self.item_name}')>"

# Event listener to generate custom IDs
@event.listens_for(Transaction, "before_insert")
def generate_transaction_id(mapper, connection, target):
    type_code_map = {
        "partition": "P",
        "container": "C",
        "large_item": "L"
    }
    type_code = type_code_map.get(target.item_type.value, "X")
    prefix = f"T-{type_code}"

    # Query the max existing number for this type
    result = connection.execute(
        text(f"SELECT id FROM transactions WHERE id LIKE '{prefix}%' ORDER BY id DESC LIMIT 1")
    ).fetchone()

    if result is None:
        next_number = 1
    else:
        last_id = result[0]  # e.g., "T-P012"
        # Extract number part after the prefix
        last_number_str = last_id.replace(prefix, "")
        last_number = int(last_number_str)
        next_number = last_number + 1

    # Zero-pad for nice formatting
    target.id = f"{prefix}{str(next_number).zfill(3)}"
