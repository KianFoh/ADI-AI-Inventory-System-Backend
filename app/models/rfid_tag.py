from sqlalchemy import Column, String, Boolean, event, text
from sqlalchemy.orm import relationship
from app.database import Base

class RFIDTag(Base):
    __tablename__ = "rfid_tags"

    id = Column(String(255), primary_key=True, index=True)
    assigned = Column(Boolean, default=False, nullable=False)

    partition = relationship("Partition", back_populates="rfid_tag", uselist=False)
    large_item = relationship("LargeItem", back_populates="rfid_tag", uselist=False)
    container = relationship("Container", back_populates="rfid_tag", uselist=False)
    
    def __repr__(self):
        return f"<RFIDTag(id='{self.id}', assigned={self.assigned})>"

@event.listens_for(RFIDTag, "before_insert")
def generate_rfid_id(mapper, connection, target):
    prefix = "RF"
    seq_name = "rfid_seq"

    # ensure sequence exists (or create via migration in production)
    connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))

    # atomically get next value
    next_val = connection.execute(text(f"SELECT nextval('{seq_name}')")).scalar()
    target.id = f"{prefix}{int(next_val)}"