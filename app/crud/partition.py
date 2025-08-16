from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.partition import Partition, PartitionStatus
from app.models.item import Item, ItemType
from app.models.storage_section import StorageSection
from app.models.rfid_tag import RFIDTag
from app.schemas.partition import PartitionCreate, PartitionUpdate
from app.crud.general import (
    create_entity_with_rfid_and_storage, 
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage
)
from typing import List, Optional, Tuple

def get_partition(db: Session, partition_id: str) -> Optional[Partition]:
    """Get partition by ID"""
    return db.query(Partition).filter(Partition.id == partition_id).first()

def get_partitions(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    status: Optional[PartitionStatus] = None
) -> Tuple[List[Partition], int]:
    """Get partitions with pagination and filtering"""
    query = db.query(Partition)
    
    if search:
        search_term = f"%{search}%"
        query = query.join(Item).join(StorageSection).filter(
            or_(
                Partition.id.ilike(search_term),
                Item.name.ilike(search_term),
                StorageSection.id.ilike(search_term)
            )
        )
    
    if status:
        query = query.filter(Partition.status == status)
    
    query = query.order_by(Partition.id)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    partitions = query.offset(skip).limit(page_size).all()
    
    return partitions, total_count

def create_partition(db: Session, partition: PartitionCreate) -> Partition:
    """Create new partition using generic function"""
    
    entity_data = {
        'item_id': partition.item_id,
        'storage_section_id': partition.storage_section_id,
        'rfid_tag_id': partition.rfid_tag_id,
        'quantity': partition.quantity,
        'status': PartitionStatus.AVAILABLE
    }
    
    return create_entity_with_rfid_and_storage(
        db=db,
        entity_class=Partition,
        entity_data=entity_data,
        item_id=partition.item_id,
        storage_section_id=partition.storage_section_id,
        rfid_tag_id=partition.rfid_tag_id,
        expected_item_type=ItemType.PARTITION
    )

def update_partition(db: Session, partition_id: str, partition: PartitionUpdate) -> Optional[Partition]:
    """Update partition using generic function"""
    update_data = partition.model_dump(exclude_unset=True)
    
    return update_entity_with_rfid_and_storage(
        db=db,
        entity_class=Partition,
        entity_id=partition_id,
        update_data=update_data,
        expected_item_type=ItemType.PARTITION
    )

def delete_partition(db: Session, partition_id: str) -> Optional[Partition]:
    """Delete partition using generic function"""
    return delete_entity_with_rfid_and_storage(db, Partition, partition_id)

def get_partitions_by_item(db: Session, item_id: str) -> List[Partition]:
    """Get partitions by item ID"""
    return db.query(Partition).filter(Partition.item_id == item_id).order_by(Partition.id).all()

def get_partitions_by_storage_section(db: Session, storage_section_id: str) -> List[Partition]:
    """Get partitions by storage section ID"""
    return db.query(Partition).filter(Partition.storage_section_id == storage_section_id).order_by(Partition.id).all()

def get_partition_count(db: Session) -> int:
    """Get total partition count"""
    return db.query(Partition).count()