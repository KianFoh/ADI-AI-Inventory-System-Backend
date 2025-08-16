from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.container import Container, ContainerStatus
from app.models.item import ItemType
from app.schemas.container import ContainerCreate, ContainerUpdate
from app.crud.general import (
    create_entity_with_rfid_and_storage,
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage
)
from typing import List, Optional, Tuple
import math


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

    query = query.order_by(Container.id)
    total_count = query.count()

    skip = (page - 1) * page_size
    containers = query.offset(skip).limit(page_size).all()

    return containers, total_count


def calculate_quantity(db: Session, item_id: str, items_weight: float) -> Optional[int]:
    from app.models.item import Item
    item = db.query(Item).filter(Item.id == item_id).first()
    if item and getattr(item, "container_item_weight", None):
        return int(math.ceil(items_weight / item.container_item_weight))
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

    return create_entity_with_rfid_and_storage(
        db=db,
        entity_class=Container,
        entity_data=entity_data,
        item_id=container.item_id,
        storage_section_id=container.storage_section_id,
        rfid_tag_id=container.rfid_tag_id,
        expected_item_type=ItemType.CONTAINER,
    )

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
    return update_entity_with_rfid_and_storage(
        db=db,
        entity_class=Container,
        entity_id=container_id,
        update_data=update_data,
        expected_item_type=ItemType.CONTAINER,
    )


def delete_container(db: Session, container_id: str) -> Optional[Container]:
    """Delete container using generic CRUD function"""
    return delete_entity_with_rfid_and_storage(db, Container, container_id)


def get_containers_by_item(db: Session, item_id: str) -> List[Container]:
    """Get all containers for a specific item"""
    return (
        db.query(Container)
        .filter(Container.item_id == item_id)
        .order_by(Container.id)
        .all()
    )


def get_containers_by_storage_section(db: Session, storage_section_id: str) -> List[Container]:
    """Get all containers in a storage section"""
    return (
        db.query(Container)
        .filter(Container.storage_section_id == storage_section_id)
        .order_by(Container.id)
        .all()
    )


def get_container_count(db: Session) -> int:
    """Get total container count"""
    return db.query(Container).count()
