from sqlalchemy import Column, String, Integer, Enum, DateTime, event, Float, text
from app.database import Base
from datetime import datetime, timezone
import enum

class TransactionType(enum.Enum):
    WITHDRAW = "withdraw"
    RETURN = "return"
    CONSUMED = "consumed"
    REGISTER = "register"

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
    # Use a DB sequence per item-type to avoid race conditions and duplicate PKs.
    type_code_map = {
        "partition": "P",
        "container": "C",
        "large_item": "L"
    }
    # safe mapping from enum value to short code
    type_code = type_code_map.get(target.item_type.value, "X")
    seq_name = f"transactions_seq_{type_code}"

    # create the sequence if it doesn't exist (safe to run every time)
    connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name}"))

    # atomically get the next value
    next_val = connection.execute(text(f"SELECT nextval('{seq_name}')")).fetchone()[0]
    next_number = int(next_val)

    # format ID consistently (zero-padded)
    target.id = f"T-{type_code}{str(next_number).zfill(3)}"
