from sqlalchemy import Column, String, Integer, Enum, Float, ForeignKey, DateTime, func, event, text
from sqlalchemy.orm import relationship
from app.database import Base
import enum
import uuid

class ItemType(enum.Enum):
    PARTITION = "partition"
    LARGE_ITEM = "large_item"
    CONTAINER = "container"

class MeasureMethod(enum.Enum):
    VISION = "vision"
    WEIGHT = "weight"

# unified stock status enum for per-type stat rows
class StockStatus(enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class Item(Base):
    __tablename__ = "items"

    id = Column(String(255), primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    manufacturer = Column(String(255), nullable=True, index=True)
    item_type = Column(Enum(ItemType), nullable=False)
    measure_method = Column(Enum(MeasureMethod), nullable=True)
    image_path = Column(String(500), nullable=True)

    process = Column(String(50), nullable=False, index=True)
    tooling_used = Column(String(255), nullable=True)
    vendor_pn = Column(String(255), nullable=True)
    sap_pn = Column(String(255), nullable=True)         
    package_used = Column(String(255), nullable=True)

    # Relationships
    partitions = relationship("Partition", back_populates="item")
    large_items = relationship("LargeItem", back_populates="item")
    containers = relationship("Container", back_populates="item")

    # per-type one-to-one stat relationships
    partition_stat = relationship("PartitionStat", uselist=False, back_populates="item", cascade="all, delete-orphan")
    largeitem_stat = relationship("LargeItemStat", uselist=False, back_populates="item", cascade="all, delete-orphan")
    container_stat = relationship("ContainerStat", uselist=False, back_populates="item", cascade="all, delete-orphan")

    # historical snapshots (ItemStatHistory) should be removed when the Item is deleted
    item_stat_history = relationship(
        "ItemStatHistory",
        back_populates="item",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
 
# Per-type stat tables
class PartitionStat(Base):
    __tablename__ = "partition_stats"
    item_id = Column(String(255), ForeignKey("items.id"), primary_key=True, index=True)
    # keep per-partition totals / thresholds here
    total_quantity = Column(Integer, nullable=True)
    total_capacity = Column(Integer, nullable=True)
    # original partition_capacity (moved here)
    partition_capacity = Column(Integer, nullable=True)
    # unified threshold names
    high_threshold = Column(Float, nullable=False)   # percent 0-100 (required)
    low_threshold = Column(Float, nullable=False)    # percent 0-100 (required)
    # optional overall status for this stat row
    stock_status = Column(Enum(StockStatus), nullable=True, index=True)

    item = relationship("Item", back_populates="partition_stat")

    def __repr__(self):
        return f"<PartitionStat(item_id='{self.item_id}', total_quantity={self.total_quantity})>"
 
class ContainerStat(Base):
    __tablename__ = "container_stats"
    item_id = Column(String(255), ForeignKey("items.id"), primary_key=True, index=True)
    # container-specific weights moved here
    container_item_weight = Column(Float, nullable=True)
    container_weight = Column(Float, nullable=True)
    # aggregated container totals / thresholds
    total_weight = Column(Float, nullable=True)
    total_quantity = Column(Integer, nullable=True)
    # unified threshold names
    high_threshold = Column(Float, nullable=False)
    low_threshold = Column(Float, nullable=False)
    stock_status = Column(Enum(StockStatus), nullable=True, index=True)

    item = relationship("Item", back_populates="container_stat")

    def __repr__(self):
        return f"<ContainerStat(item_id='{self.item_id}', total_weight={self.total_weight}, total_quantity={self.total_quantity})>"
 
class LargeItemStat(Base):
    __tablename__ = "largeitem_stats"
    item_id = Column(String(255), ForeignKey("items.id"), primary_key=True, index=True)
    total_quantity = Column(Integer, nullable=True)
    # unified threshold names (integers for large items)
    high_threshold = Column(Integer, nullable=False)
    low_threshold = Column(Integer, nullable=False)
    stock_status = Column(Enum(StockStatus), nullable=True, index=True)
 
    item = relationship("Item", back_populates="largeitem_stat")

# New table for dashboard / historical snapshots
class ItemStatHistory(Base):
    __tablename__ = "item_stat_history"

    # use short human-readable IDs like "H-P1", "H-C2", "H-L3"
    id = Column(String(20), primary_key=True, index=True)

    # Snapshot metadata
    timestamp = Column(DateTime, default=func.now(), nullable=False)
    # reference items.id with ON DELETE CASCADE so DB will remove history when item deleted
    item_id = Column(String(255), ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    item_name = Column(String(255), nullable=False)
    item_type = Column(Enum(ItemType), nullable=False)

    # Snapshotted stat values
    total_quantity = Column(Float, nullable=True)
    total_capacity = Column(Float, nullable=True)
    total_weight = Column(Float, nullable=True)
    stock_status = Column(Enum(StockStatus), nullable=True, index=True)

    # Optional metadata
    change_source = Column(String(255), nullable=True)
 
    # ORM relationship back to the Item
    item = relationship("Item", back_populates="item_stat_history", passive_deletes=True)

    def __repr__(self):
        return f"<ItemStatHistory(id='{self.id}', item_id='{self.item_id}', timestamp={self.timestamp})>"


# Event listener to generate short IDs for ItemStatHistory ("H-<code><n>")
@event.listens_for(ItemStatHistory, "before_insert")
def generate_item_stat_history_id(mapper, connection, target):
    type_code_map = {
        "partition": "P",
        "container": "C",
        "large_item": "L"
    }
    # support Enum or raw string
    type_val = getattr(target.item_type, "value", target.item_type)
    type_code = type_code_map.get(type_val, "X")
    prefix = f"ISH-{type_code}"

    # Find last id with this prefix
    result = connection.execute(
        text("SELECT id FROM item_stat_history WHERE id LIKE :lk ORDER BY id DESC LIMIT 1"),
        {"lk": f"{prefix}%" }
    ).fetchone()

    if result is None:
        next_number = 1
    else:
        last_id = result[0]
        last_number_str = last_id.replace(prefix, "")
        try:
            last_number = int(last_number_str)
        except Exception:
            last_number = 0
        next_number = last_number + 1

    target.id = f"{prefix}{next_number}"

