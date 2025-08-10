from sqlalchemy import Column, String, Integer, Enum as SQLEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from typing import List, TYPE_CHECKING
from app.database import Base
from enum import Enum

if TYPE_CHECKING:
    from app.models.partition import Partition
    from app.models.large_item import LargeItem

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
    total_units: Mapped[int] = mapped_column(Integer, nullable=False)
    used_units: Mapped[int] = mapped_column(Integer, default=0)

    partitions = relationship("Partition", back_populates="storage_section", cascade="all, delete-orphan")
    large_items = relationship("LargeItem", back_populates="storage_section", cascade="all, delete-orphan")


    @staticmethod
    def generate_id(floor: str, cabinet: str, layer: str, color: str) -> str:
        """Generate storage section ID from components"""
        color_code = color.upper()[0] if color else "X"
        return f"{floor}-{cabinet}-{layer}-{color_code}"

    @property
    def available_units(self) -> int:
        """Calculate available units"""
        return max(0, self.total_units - self.used_units)

    @property
    def utilization_rate(self) -> float:
        """Calculate utilization rate (0.0 to 1.0)"""
        if self.total_units == 0:
            return 0.0
        return min(1.0, self.used_units / self.total_units)

    @property
    def is_full(self) -> bool:
        """Check if section is at capacity"""
        return self.used_units >= self.total_units

    @property
    def is_empty(self) -> bool:
        """Check if section is empty"""
        return self.used_units == 0

    def __repr__(self):
        return f"<StorageSection(id={self.id}, floor={self.floor}, cabinet={self.cabinet}, layer={self.layer}, color={self.color.value}, used/total={self.used_units}/{self.total_units})>"