from sqlalchemy.orm import Session
from app.models.item import Item, ItemType
from app.models.storage_section import StorageSection
from app.models.rfid_tag import RFIDTag
from typing import Optional, TypeVar, Type, Dict, Any

EntityModel = TypeVar('EntityModel')


def _validate_item_type(db: Session, item_id: str, expected_type: ItemType) -> Item:
    """Validate item exists and has correct type"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise ValueError(f"Item with ID '{item_id}' not found")
    if item.item_type != expected_type:
        raise ValueError(
            f"Item '{item_id}' must be of type '{expected_type.value}', "
            f"but found '{item.item_type.value}'"
        )
    return item


def _validate_storage_section_exists(db: Session, storage_section_id: str) -> StorageSection:
    """Validate storage section exists"""
    storage_section = db.query(StorageSection).filter(StorageSection.id == storage_section_id).first()
    if not storage_section:
        raise ValueError(f"Storage section '{storage_section_id}' not found")
    return storage_section


def _assign_rfid_tag(db: Session, rfid_tag_id: str) -> RFIDTag:
    """Validate and assign RFID tag"""
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == rfid_tag_id).first()
    if not rfid_tag:
        raise ValueError(f"RFID tag '{rfid_tag_id}' not found")
    if rfid_tag.assigned:
        raise ValueError(f"RFID tag '{rfid_tag_id}' is not available")

    rfid_tag.assigned = True
    return rfid_tag


def _release_rfid_tag(db: Session, rfid_tag_id: str) -> None:
    """Release RFID tag back to available pool"""
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == rfid_tag_id).first()
    if rfid_tag:
        rfid_tag.assigned = False


def create_entity_with_rfid_and_storage(
    db: Session,
    entity_class: Type[EntityModel],
    entity_data: Dict[str, Any],
    item_id: str,
    storage_section_id: str,
    rfid_tag_id: str,
    expected_item_type: ItemType
) -> EntityModel:
    """Generic function to create entity with RFID and storage section management"""
    try:
        _validate_item_type(db, item_id, expected_item_type)
        _validate_storage_section_exists(db, storage_section_id)
        _assign_rfid_tag(db, rfid_tag_id)

        entity = entity_class(**entity_data)
        db.add(entity)
        db.commit()
        db.refresh(entity)
        return entity

    except Exception:
        db.rollback()
        raise


def delete_entity_with_rfid_and_storage(
    db: Session,
    entity_class: Type[EntityModel],
    entity_id: str
) -> Optional[EntityModel]:
    """Generic function to delete entity and release RFID"""
    try:
        entity = db.query(entity_class).filter(entity_class.id == entity_id).first()
        if not entity:
            return None

        _release_rfid_tag(db, entity.rfid_tag_id)
        db.delete(entity)
        db.commit()
        return entity

    except Exception:
        db.rollback()
        raise


def update_entity_with_rfid_and_storage(
    db: Session,
    entity_class: Type[EntityModel],
    entity_id: str,
    update_data: Dict[str, Any],
    expected_item_type: ItemType
) -> Optional[EntityModel]:
    """Generic function to update entity with RFID and storage section management"""
    db_entity = db.query(entity_class).filter(entity_class.id == entity_id).first()
    if not db_entity:
        return None

    try:
        if 'item_id' in update_data:
            new_item = db.query(Item).filter(Item.id == update_data['item_id']).first()
            if not new_item:
                raise ValueError(f"Item '{update_data['item_id']}' not found")
            if new_item.item_type != expected_item_type:
                raise ValueError(
                    f"Item '{update_data['item_id']}' must be of type {expected_item_type.value}, "
                    f"got {new_item.item_type.value}"
                )

        if 'storage_section_id' in update_data:
            _validate_storage_section_exists(db, update_data['storage_section_id'])

        if 'rfid_tag_id' in update_data and update_data['rfid_tag_id'] != db_entity.rfid_tag_id:
            old_rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == db_entity.rfid_tag_id).first()
            new_rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == update_data['rfid_tag_id']).first()
            if not new_rfid_tag:
                raise ValueError(f"RFID tag '{update_data['rfid_tag_id']}' not found")
            if new_rfid_tag.assigned:
                raise ValueError(f"RFID tag '{update_data['rfid_tag_id']}' is already assigned")
            if old_rfid_tag:
                old_rfid_tag.assigned = False
            new_rfid_tag.assigned = True

        for key, value in update_data.items():
            if hasattr(db_entity, key):
                setattr(db_entity, key, value)

        db.commit()
        db.refresh(db_entity)
        return db_entity

    except Exception:
        db.rollback()
        raise
