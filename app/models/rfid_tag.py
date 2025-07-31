from sqlalchemy import Column, String, Boolean
from app.database import Base

class RFIDTag(Base):
    __tablename__ = "rfid_tags"

    id = Column(String(255), primary_key=True, index=True)
    assigned = Column(Boolean, default=False, nullable=False)
    
    def __repr__(self):
        return f"<RFIDTag(id='{self.id}', assigned={self.assigned})>"