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
    result = connection.execute(
        text(f"SELECT id FROM rfid_tags WHERE id LIKE '{prefix}%' ORDER BY CAST(SUBSTRING(id, 3) AS INTEGER) DESC LIMIT 1")
    ).fetchone()
    if result is None:
        next_number = 1
    else:
        last_id = result[0]
        last_number = int(last_id[2:]) 
        next_number = last_number + 1
    target.id = f"{prefix}{next_number}"