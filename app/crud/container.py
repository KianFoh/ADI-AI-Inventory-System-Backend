from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.container import Container, ContainerStatus
from app.models.item import ItemType
from app.schemas.container import ContainerCreate, ContainerUpdate, ContainerResponse
from app.crud.general import (
    create_entity_with_rfid_and_storage,
    delete_entity_with_rfid_and_storage,
    update_entity_with_rfid_and_storage
)
from typing import List, Optional, Tuple

def get_container(db: Session, container_id: str) -> Optional[Container]:
    return db.query(Container).filter(Container.id == container_id).first()

def get_containers(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: Optional[str] = None,
    status: Optional[ContainerStatus] = None
) -> Tuple[List[Container], int]:
    query = db.query(Container)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Container.id.ilike(search_term),
                Container.rfid_tag_id.ilike(search_term),
                Container.storage_section_id.ilike(search_term)
            )
        )
    if status:
        query = query.filter(Container.status == status)
    query = query.order_by(Container.id)
    total_count = query.count()
    skip = (page - 1) * page_size
    containers = query.offset(skip).limit(page_size).all()
    return containers, total_count

def create_container(db: Session, container: ContainerCreate) -> Container:
    entity_data = {
        'item_id': container.item_id,
        'storage_section_id': container.storage_section_id,
        'rfid_tag_id': container.rfid_tag_id,
        'weight': container.weight,
        'container_weight': container.container_weight,
        'status': ContainerStatus.AVAILABLE
    }
    return create_entity_with_rfid_and_storage(
        db=db,
        entity_class=Container,
        entity_data=entity_data,
        item_id=container.item_id,
        storage_section_id=container.storage_section_id,
        rfid_tag_id=container.rfid_tag_id,
        expected_item_type=ItemType.CONTAINER
    )

def update_container(db: Session, container_id: str, container: ContainerUpdate) -> Optional[Container]:
    update_data = container.model_dump(exclude_unset=True)
    return update_entity_with_rfid_and_storage(
        db=db,
        entity_class=Container,
        entity_id=container_id,
        update_data=update_data,
        expected_item_type=ItemType.CONTAINER
    )

def delete_container(db: Session, container_id: str) -> Optional[Container]:
    return delete_entity_with_rfid_and_storage(db, Container, container_id)

def get_containers_by_item(db: Session, item_id: str) -> List[Container]:
    return db.query(Container).filter(Container.item_id == item_id).order_by(Container.id).all()

def get_containers_by_storage_section(db: Session, storage_section_id: str) -> List[Container]:
    return db.query(Container).filter(Container.storage_section_id == storage_section_id).order_by(Container.id).all()

def get_container_count(db: Session) -> int:
    return db.query(Container).count()