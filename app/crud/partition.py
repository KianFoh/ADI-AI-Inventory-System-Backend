from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.partition import Partition, PartitionStatus
from app.models.item import Item, ItemType, PartitionStat
from app.models.storage_section import StorageSection
from app.schemas.partition import PartitionCreate, PartitionUpdate
from app.crud.general import (
    create_entity_with_rfid_and_storage, 
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage
)
from typing import List, Optional, Tuple
# import updater
from app.crud.item import _update_partition_status
from app.crud.general import order_by_numeric_suffix

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
    
    # order by numeric suffix of id (Postgres). Falls back to string id for deterministic ordering.
    query = order_by_numeric_suffix(query, Partition.id, asc=True)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    partitions = query.offset(skip).limit(page_size).all()
    
    return partitions, total_count

def create_partition(db: Session, partition: PartitionCreate) -> Partition:
    """Create new partition using generic function"""
    
    # enforce configured partition_capacity (backend source of truth: PartitionStat)
    from app.models.item import PartitionStat as _PartitionStat
    ps = db.query(_PartitionStat).filter(_PartitionStat.item_id == partition.item_id).first()
    if ps and ps.partition_capacity is not None:
        try:
            cap = int(ps.partition_capacity)
            if partition.quantity is not None and int(partition.quantity) > cap:
                raise ValueError({"field": "quantity", "message": f"quantity ({partition.quantity}) exceeds partition_capacity ({cap})"})
        except ValueError:
            # re-raise structured errors
            raise
        except Exception:
            # fallthrough if conversion fails (unlikely); allow backend to handle
            pass

    entity_data = {
        'item_id': partition.item_id,
        'storage_section_id': partition.storage_section_id,
        'rfid_tag_id': partition.rfid_tag_id,
        'quantity': partition.quantity,
        'status': PartitionStatus.AVAILABLE
    }
    
    created = create_entity_with_rfid_and_storage(
        db=db,
        entity_class=Partition,
        entity_data=entity_data,
        item_id=partition.item_id,
        storage_section_id=partition.storage_section_id,
        rfid_tag_id=partition.rfid_tag_id,
        expected_item_type=ItemType.PARTITION
    )
    # ensure stats (including stock_status) are recomputed & persisted
    try:
        db.refresh(created)
        _update_partition_status(db, created.item_id, "Register Partition")
        # refresh the parent Item so response readers see updated partition_stat
        item = db.query(Item).filter(Item.id == created.item_id).first()
        if item:
            db.refresh(item)
    except Exception:
        pass
    return created

def update_partition(db: Session, partition_id: str, partition: PartitionUpdate) -> Optional[Partition]:
    """Update partition using generic function"""
    update_data = partition.model_dump(exclude_unset=True)

    # determine final target item_id for this partition after update
    current = db.query(Partition).filter(Partition.id == partition_id).first()
    target_item_id = update_data.get("item_id") if update_data.get("item_id") is not None else (current.item_id if current else None)
    # determine final quantity after update
    target_quantity = update_data.get("quantity") if update_data.get("quantity") is not None else (current.quantity if current else None)

    # enforce configured partition_capacity on the target item (if configured)
    if target_item_id and target_quantity is not None:
        ps = db.query(PartitionStat).filter(PartitionStat.item_id == target_item_id).first()
        if ps and ps.partition_capacity is not None:
            try:
                cap = int(ps.partition_capacity)
                if int(target_quantity) > cap:
                    raise ValueError({"field": "quantity", "message": f"quantity ({target_quantity}) exceeds partition_capacity ({cap})"})
            except ValueError:
                raise
            except Exception:
                # don't block update on unexpected conversion/db errors here
                pass

    updated = update_entity_with_rfid_and_storage(
        db=db,
        entity_class=Partition,
        entity_id=partition_id,
        update_data=update_data,
        expected_item_type=ItemType.PARTITION
    )
    if updated:
        try:
            db.refresh(updated)
            _update_partition_status(db, updated.item_id, "Return Partition")
            item = db.query(Item).filter(Item.id == updated.item_id).first()
            if item:
                db.refresh(item)
        except Exception:
            pass
    return updated

def delete_partition(db: Session, partition_id: str) -> Optional[Partition]:
    """Delete partition using generic function"""
    current = db.query(Partition).filter(Partition.id == partition_id).first()
    item_id = current.item_id if current else None
    deleted = delete_entity_with_rfid_and_storage(db, Partition, partition_id)
    if deleted and item_id:
        try:
            _update_partition_status(db, item_id, "Partition Consumed")
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                db.refresh(item)
        except Exception:
            pass
    return deleted

def get_partitions_by_item(db: Session, item_id: str) -> List[Partition]:
    """Get partitions by item ID"""
    query = db.query(Partition).filter(Partition.item_id == item_id)
    query = order_by_numeric_suffix(query, Partition.id)
    return query.all()

def get_partitions_by_storage_section(db: Session, storage_section_id: str) -> List[Partition]:
    """Get partitions by storage section ID"""
    query = db.query(Partition).filter(Partition.storage_section_id == storage_section_id)
    query = order_by_numeric_suffix(query, Partition.id)
    return query.all()

def get_partition_count(db: Session) -> int:
    """Get total partition count"""
    return db.query(Partition).count()