from sqlalchemy import Column, String, Integer, ForeignKey, Enum, event, text
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class PartitionStatus(enum.Enum):
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"

class Partition(Base):
    __tablename__ = "partitions"

    id = Column(String(20), primary_key=True, index=True)
    item_id = Column(String(255), ForeignKey("items.id"), nullable=False, index=True)
    storage_section_id = Column(String(255), ForeignKey("storage_sections.id"), nullable=False, index=True)
    rfid_tag_id = Column(String(255), ForeignKey("rfid_tags.id"), nullable=False, index=True)
    
    quantity = Column(Integer, nullable=False, default=0)
    status = Column(Enum(PartitionStatus), nullable=False, default=PartitionStatus.AVAILABLE, index=True)
    
    # Relationships
    item = relationship("Item", back_populates="partitions")
    storage_section = relationship("StorageSection", back_populates="partitions")
    rfid_tag = relationship("RFIDTag", back_populates="partition")
    
    def __repr__(self):
        return f"<Partition(id='{self.id}', quantity={self.quantity}, status='{self.status.value}')>"

# Event listener to generate sequential Partition IDs
@event.listens_for(Partition, "before_insert")
def generate_partition_id(mapper, connection, target):
    prefix = "P"
    seq_name = "partitions_seq"

    # ensure sequence exists (prefer to create via migration in production)
    connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))

    # atomically get next value
    next_val = connection.execute(text(f"SELECT nextval('{seq_name}')")).scalar()
    target.id = f"{prefix}{int(next_val)}"
