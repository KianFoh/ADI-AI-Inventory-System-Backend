from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.models.partition import Partition, PartitionStatus
from app.models.rfid_tag import RFIDTag
from app.models.item import Item
from app.models.storage_section import StorageSection
from app.schemas.partition import PartitionCreate, PartitionUpdate
from typing import List, Optional, Tuple

def get_partition(db: Session, partition_id: str) -> Optional[Partition]:
    return db.query(Partition).filter(Partition.id == partition_id).first()

def get_partitions(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    has_rfid: Optional[bool] = None,
    status: Optional[PartitionStatus] = None
) -> Tuple[List[Partition], int]:
    """Get partitions with pagination"""
    query = db.query(Partition)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Partition.id.ilike(search_term),
                Partition.item_id.ilike(search_term),
                Partition.storage_section_id.ilike(search_term),
                Partition.rfid_tag_id.ilike(search_term)
            )
        )
    
    if has_rfid is not None:
        if has_rfid:
            query = query.filter(Partition.rfid_tag_id.isnot(None))
        else:
            query = query.filter(Partition.rfid_tag_id.is_(None))
    
    if status:
        query = query.filter(Partition.status == status)
    
    query = query.order_by(Partition.id)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    partitions = query.offset(skip).limit(page_size).all()
    
    return partitions, total_count

def create_partition(db: Session, partition: PartitionCreate) -> Partition:
    """Create new partition with RFID automatically assigned"""
    # Validate item exists
    item = db.query(Item).filter(Item.id == partition.item_id).first()
    if not item:
        raise ValueError(f"Item {partition.item_id} not found")
    
    # Validate storage section exists
    storage_section = db.query(StorageSection).filter(StorageSection.id == partition.storage_section_id).first()
    if not storage_section:
        raise ValueError(f"Storage section {partition.storage_section_id} not found")
    
    # Validate RFID tag exists and is available
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == partition.rfid_tag_id).first()
    if not rfid_tag:
        raise ValueError(f"RFID tag {partition.rfid_tag_id} not found")
    
    if rfid_tag.assigned:
        raise ValueError(f"RFID tag {partition.rfid_tag_id} is already assigned")
    
    # Check storage section capacity
    current_used = storage_section.used_units + item.unit
    if current_used > storage_section.total_units:
        raise ValueError(f"Storage section {partition.storage_section_id} does not have enough capacity")
    
    db_partition = Partition(
        item_id=partition.item_id,
        storage_section_id=partition.storage_section_id,
        rfid_tag_id=partition.rfid_tag_id,
        capacity=partition.capacity,
        quantity=0,
        status=PartitionStatus.AVAILABLE
    )
    
    # Update related entities
    rfid_tag.assigned = True
    storage_section.used_units += item.unit
    
    db.add(db_partition)
    db.commit()
    db.refresh(db_partition)
    
    return db_partition

def update_partition(db: Session, partition_id: str, partition: PartitionUpdate) -> Optional[Partition]:
    """Update partition (RFID tag cannot be changed)"""
    db_partition = db.query(Partition).filter(Partition.id == partition_id).first()
    if not db_partition:
        return None
    
    update_data = partition.model_dump(exclude_unset=True)
    
    # Validate capacity changes
    if 'capacity' in update_data:
        new_capacity = update_data['capacity']
        if db_partition.quantity > new_capacity:
            raise ValueError(f"Cannot reduce capacity to {new_capacity}. Current quantity is {db_partition.quantity}")
    
    # Validate quantity changes
    if 'quantity' in update_data:
        new_quantity = update_data['quantity']
        capacity = update_data.get('capacity', db_partition.capacity)
        if new_quantity > capacity:
            raise ValueError(f"Quantity ({new_quantity}) cannot exceed capacity ({capacity})")
        if new_quantity < 0:
            raise ValueError("Quantity cannot be negative")
    
    # Validate storage section change
    if 'storage_section_id' in update_data:
        new_section_id = update_data['storage_section_id']
        if new_section_id != db_partition.storage_section_id:
            # Check new section exists and has capacity
            new_section = db.query(StorageSection).filter(StorageSection.id == new_section_id).first()
            if not new_section:
                raise ValueError(f"Storage section {new_section_id} not found")
            
            item = db.query(Item).filter(Item.id == db_partition.item_id).first()
            if new_section.used_units + item.unit > new_section.total_units:
                raise ValueError(f"Storage section {new_section_id} does not have enough capacity")
            
            # Update both sections
            old_section = db.query(StorageSection).filter(StorageSection.id == db_partition.storage_section_id).first()
            if old_section:
                old_section.used_units -= item.unit
            new_section.used_units += item.unit
    
    for key, value in update_data.items():
        setattr(db_partition, key, value)
    
    db.commit()
    db.refresh(db_partition)
    return db_partition

def delete_partition(db: Session, partition_id: str) -> Optional[Partition]:
    """Delete partition and automatically unassign RFID tag"""
    db_partition = db.query(Partition).filter(Partition.id == partition_id).first()
    if not db_partition:
        return None
    
    # Release RFID tag
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == db_partition.rfid_tag_id).first()
    if rfid_tag:
        rfid_tag.assigned = False
    
    # Update storage section
    storage_section = db.query(StorageSection).filter(StorageSection.id == db_partition.storage_section_id).first()
    if storage_section:
        item = db.query(Item).filter(Item.id == db_partition.item_id).first()
        if item:
            storage_section.used_units -= item.unit
    
    db.delete(db_partition)
    db.commit()
    
    return db_partition

def update_partition_status(db: Session, partition_id: str, status: PartitionStatus) -> Optional[Partition]:
    db_partition = db.query(Partition).filter(Partition.id == partition_id).first()
    if not db_partition:
        return None
    
    db_partition.status = status
    db.commit()
    db.refresh(db_partition)
    return db_partition

def get_partitions_by_status(db: Session, status: PartitionStatus) -> List[Partition]:
    return db.query(Partition).filter(Partition.status == status).order_by(Partition.id).all()

def get_available_partitions(db: Session) -> List[Partition]:
    return db.query(Partition).filter(Partition.status == PartitionStatus.AVAILABLE).order_by(Partition.id).all()

def get_partitions_by_item(db: Session, item_id: str) -> List[Partition]:
    return db.query(Partition).filter(Partition.item_id == item_id).order_by(Partition.id).all()

def get_partitions_by_storage_section(db: Session, storage_section_id: str) -> List[Partition]:
    return db.query(Partition).filter(Partition.storage_section_id == storage_section_id).order_by(Partition.id).all()

def get_partition_count(db: Session) -> int:
    return db.query(Partition).count()

def get_partition_count_by_status(db: Session, status: PartitionStatus) -> int:
    return db.query(Partition).filter(Partition.status == status).count()

def update_partition_quantity(db: Session, partition_id: str, new_quantity: int) -> Optional[Partition]:
    db_partition = db.query(Partition).filter(Partition.id == partition_id).first()
    if not db_partition:
        return None
    
    if new_quantity < 0:
        raise ValueError("Quantity cannot be negative")
    
    if new_quantity > db_partition.capacity:
        raise ValueError(f"Quantity ({new_quantity}) cannot exceed capacity ({db_partition.capacity})")
    
    db_partition.quantity = new_quantity
    db.commit()
    db.refresh(db_partition)
    return db_partition