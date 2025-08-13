from sqlalchemy import Column, String, Boolean
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