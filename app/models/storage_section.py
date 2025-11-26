from sqlalchemy import String,Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.database import Base
from enum import Enum

class SectionColor(Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"
    YELLOW = "yellow"

class StorageSection(Base):
    __tablename__ = "storage_sections"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    floor: Mapped[str] = mapped_column(String(50), nullable=False)
    cabinet: Mapped[str] = mapped_column(String(50), nullable=False) 
    layer: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[SectionColor] = mapped_column(SQLEnum(SectionColor), nullable=False)

    partitions = relationship("Partition", back_populates="storage_section", cascade="all, delete-orphan")
    large_items = relationship("LargeItem", back_populates="storage_section", cascade="all, delete-orphan")
    containers = relationship("Container", back_populates="storage_section")


    @staticmethod
    def generate_id(floor: str, cabinet: str, layer: str, color: str) -> str:
        """Generate storage section ID from components"""
        color_code = color.upper()[0] if color else "X"
        return f"{floor}-{cabinet}-{layer}-{color_code}"


    def __repr__(self):
        return f"<StorageSection(id={self.id}, floor={self.floor}, cabinet={self.cabinet}, layer={self.layer}, color={self.color.value})>"