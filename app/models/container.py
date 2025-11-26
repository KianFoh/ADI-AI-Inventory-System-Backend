from sqlalchemy import Column, String, Integer, Float, ForeignKey, Enum, event, text
from sqlalchemy.orm import relationship
from app.database import Base
import enum

class ContainerStatus(enum.Enum):
    AVAILABLE = "available"
    WITHDRAWN = "withdrawn"


class Container(Base):
    __tablename__ = "containers"

    id = Column(String(20), primary_key=True, index=True)  # will be C1, C2, ...
    item_id = Column(String(255), ForeignKey("items.id"), nullable=False, index=True)
    storage_section_id = Column(String(255), ForeignKey("storage_sections.id"), nullable=False, index=True)
    rfid_tag_id = Column(String(255), ForeignKey("rfid_tags.id"), nullable=False, index=True)

    # Always store total weight of items inside this container
    items_weight = Column(Float, nullable=False, default=0.0)

    # Optional manual quantity (kept in case you need explicit tracking)
    quantity = Column(Integer, nullable=True)

    status = Column(Enum(ContainerStatus), nullable=False, default=ContainerStatus.AVAILABLE, index=True)

    # Relationships
    item = relationship("Item", back_populates="containers")
    storage_section = relationship("StorageSection", back_populates="containers")
    rfid_tag = relationship("RFIDTag", back_populates="container")

    @property
    def calculated_quantity(self):
        """
        Returns quantity derived from items_weight // container_item_weight
        if the referenced item defines container_item_weight.
        """
        if self.item and getattr(self.item, "container_item_weight", None):
            return int(self.items_weight // self.item.container_item_weight)
        return None

    def __repr__(self):
        return (
            f"<Container(id='{self.id}', "
            f"items_weight={self.items_weight}kg, "
            f"calculated_quantity={self.calculated_quantity}, "
            f"quantity={self.quantity}, "
            f"status='{self.status.value}')>"
        )


# Event listener to generate sequential Container IDs
@event.listens_for(Container, "before_insert")
def generate_container_id(mapper, connection, target):
    prefix = "C"
    seq_name = "containers_seq"

    # create sequence if it doesn't exist (prefer to provision via migration in production)
    try:
        connection.execute(text(f"CREATE SEQUENCE IF NOT EXISTS {seq_name} START 1"))
    except Exception:
        pass

    # atomically get the next value
    next_val = connection.execute(text(f"SELECT nextval('{seq_name}')")).scalar()
    target.id = f"{prefix}{int(next_val)}"
