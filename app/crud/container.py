from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.container import Container, ContainerStatus
from app.models.item import Item, ItemType, ContainerStat
from app.schemas.container import ContainerCreate, ContainerUpdate
from app.crud.general import (
    create_entity_with_rfid_and_storage,
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage,
    order_by_numeric_suffix
)
from typing import List, Optional, Tuple
import math
# call status updater from item CRUD
from app.crud.item import _update_container_status


def get_container(db: Session, container_id: str) -> Optional[Container]:
    """Get container by ID"""
    return db.query(Container).filter(Container.id == container_id).first()


def get_containers(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    status: Optional[ContainerStatus] = None
) -> Tuple[List[Container], int]:
    """Get containers with optional search and status filter"""
    query = db.query(Container)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Container.id.ilike(search_term),
                Container.rfid_tag_id.ilike(search_term),
                Container.storage_section_id.ilike(search_term),
            )
        )

    if status:
        query = query.filter(Container.status == status)

    # order by numeric suffix of id for human-friendly numeric ordering (Postgres)
    query = order_by_numeric_suffix(query, Container.id)
    total_count = query.count()

    skip = (page - 1) * page_size
    containers = query.offset(skip).limit(page_size).all()

    return containers, total_count


def calculate_quantity(db: Session, item_id: str, items_weight: float) -> Optional[int]:
    # Prefer configured container_item_weight from ContainerStat
    cs = db.query(ContainerStat).filter(ContainerStat.item_id == item_id).first()
    if cs and cs.container_item_weight:
        try:
            return int(round(items_weight / float(cs.container_item_weight)))

        except Exception:
            return None
    # fallback to Item only if stat not configured
    item = db.query(Item).filter(Item.id == item_id).first()
    if item and getattr(item, "container_item_weight", None):
        try:
            return int(math.ceil(items_weight / item.container_item_weight))
        except Exception:
            return None
    return None

def create_container(db: Session, container: ContainerCreate) -> Container:
    """Create new container using generic CRUD function"""
    quantity = calculate_quantity(db, container.item_id, container.items_weight)
    entity_data = {
        "item_id": container.item_id,
        "storage_section_id": container.storage_section_id,
        "rfid_tag_id": container.rfid_tag_id,
        "items_weight": container.items_weight,
        "quantity": quantity,
        "status": ContainerStatus.AVAILABLE,
    }

    created = create_entity_with_rfid_and_storage(
        db=db,
        entity_class=Container,
        entity_data=entity_data,
        item_id=container.item_id,
        storage_section_id=container.storage_section_id,
        rfid_tag_id=container.rfid_tag_id,
        expected_item_type=ItemType.CONTAINER,
    )
    try:
        db.refresh(created)
        _update_container_status(db, created.item_id, "Register Container")
        item = db.query(Item).filter(Item.id == created.item_id).first()
        if item:
            db.refresh(item)
    except Exception:
        pass
    return created

def update_container(db: Session, container_id: str, container: ContainerUpdate) -> Optional[Container]:
    """Update container using generic CRUD function"""
    update_data = container.model_dump(exclude_unset=True)
    # Recalculate quantity if items_weight or item_id is updated
    items_weight = update_data.get("items_weight")
    item_id = update_data.get("item_id")
    if items_weight is not None or item_id is not None:
        # Get current container if needed
        current = db.query(Container).filter(Container.id == container_id).first()
        if current:
            item_id = item_id if item_id is not None else current.item_id
            items_weight = items_weight if items_weight is not None else current.items_weight
            update_data["quantity"] = calculate_quantity(db, item_id, items_weight)
    updated = update_entity_with_rfid_and_storage(
        db=db,
        entity_class=Container,
        entity_id=container_id,
        update_data=update_data,
        expected_item_type=ItemType.CONTAINER,
    )
    if updated:
        try:
            db.refresh(updated)
            _update_container_status(db, updated.item_id, "Return Container")
            item = db.query(Item).filter(Item.id == updated.item_id).first()
            if item:
                db.refresh(item)
        except Exception:
            pass
    return updated

def delete_container(db: Session, container_id: str) -> Optional[Container]:
    """Delete container using generic CRUD function"""
    # fetch item_id for updater after deletion
    current = db.query(Container).filter(Container.id == container_id).first()
    item_id = current.item_id if current else None
    deleted = delete_entity_with_rfid_and_storage(db, Container, container_id)
    if deleted and item_id:
        try:
            _update_container_status(db, item_id, "Container Consumed")
            item = db.query(Item).filter(Item.id == item_id).first()
            if item:
                db.refresh(item)
        except Exception:
            pass
    return deleted


def get_containers_by_item(db: Session, item_id: str) -> List[Container]:
    """Get all containers for a specific item"""
    query = db.query(Container).filter(Container.item_id == item_id)
    query = order_by_numeric_suffix(query, Container.id)
    return query.all()

def get_containers_by_storage_section(db: Session, storage_section_id: str) -> List[Container]:
    """Get all containers in a storage section"""
    query = db.query(Container).filter(Container.storage_section_id == storage_section_id)
    query = order_by_numeric_suffix(query, Container.id)
    return query.all()


def get_container_count(db: Session) -> int:
    """Get total container count"""
    return db.query(Container).count()
