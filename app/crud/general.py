from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.item import Item, ItemType
from app.models.storage_section import StorageSection
from app.models.rfid_tag import RFIDTag
from typing import Optional, TypeVar, Type, Dict, Any

# Generic type for entity models
EntityModel = TypeVar('EntityModel')

def _validate_item_type(db: Session, item_id: str, expected_type: ItemType) -> Item:
    """Validate item exists and has correct type"""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise ValueError(f"Item with ID '{item_id}' not found")
    if item.item_type != expected_type:
        raise ValueError(f"Item '{item_id}' must be of type '{expected_type.value}', but found '{item.item_type.value}'")
    return item

def _validate_storage_section_capacity(db: Session, storage_section_id: str, required_units: int) -> StorageSection:
    """Validate storage section exists and has enough capacity"""
    storage_section = db.query(StorageSection).filter(StorageSection.id == storage_section_id).first()
    if not storage_section:
        raise ValueError(f"Storage section '{storage_section_id}' not found")
    
    if storage_section.used_units + required_units > storage_section.total_units:
        available = storage_section.total_units - storage_section.used_units
        raise ValueError(f"Storage section '{storage_section_id}' does not have enough capacity. Available: {available}, Required: {required_units}")
    
    return storage_section

def _assign_rfid_tag(db: Session, rfid_tag_id: str) -> RFIDTag:
    """Validate and assign RFID tag"""
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == rfid_tag_id).first()
    if not rfid_tag:
        raise ValueError(f"RFID tag '{rfid_tag_id}' not found")
    if rfid_tag.assigned:
        raise ValueError(f"RFID tag '{rfid_tag_id}' is not available")
    
    # Assign the tag
    rfid_tag.assigned = True
    return rfid_tag

def _release_rfid_tag(db: Session, rfid_tag_id: str) -> None:
    """Release RFID tag back to available pool"""
    rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == rfid_tag_id).first()
    if rfid_tag:
        rfid_tag.assigned = False

def _update_storage_section_units(db: Session, storage_section_id: str, unit_change: int) -> None:
    """Update storage section used units (positive to add, negative to subtract)"""
    storage_section = db.query(StorageSection).filter(StorageSection.id == storage_section_id).first()
    if storage_section:
        storage_section.used_units += unit_change

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
        # 1. Validate item type
        item = _validate_item_type(db, item_id, expected_item_type)
        
        # 2. Validate storage section capacity
        _validate_storage_section_capacity(db, storage_section_id, item.unit)
        
        # 3. Assign RFID tag
        _assign_rfid_tag(db, rfid_tag_id)
        
        # 4. Create entity
        entity = entity_class(**entity_data)
        db.add(entity)
        
        # 5. Update storage section units
        _update_storage_section_units(db, storage_section_id, item.unit)
        
        # 6. Commit all changes
        db.commit()
        db.refresh(entity)
        
        return entity
        
    except Exception as e:
        db.rollback()
        raise e

def delete_entity_with_rfid_and_storage(
    db: Session,
    entity_class: Type[EntityModel],
    entity_id: str
) -> Optional[EntityModel]:
    """Generic function to delete entity and reverse RFID/storage changes"""
    
    try:
        # Get the entity
        entity = db.query(entity_class).filter(entity_class.id == entity_id).first()
        if not entity:
            return None
        
        # Get item for unit calculation
        item = db.query(Item).filter(Item.id == entity.item_id).first()
        
        # 1. Release RFID tag
        _release_rfid_tag(db, entity.rfid_tag_id)
        
        # 2. Return storage section units
        if item:
            _update_storage_section_units(db, entity.storage_section_id, -item.unit)
        
        # 3. Delete entity
        db.delete(entity)
        
        # 4. Commit changes
        db.commit()
        
        return entity
        
    except Exception as e:
        db.rollback()
        raise e

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
        old_item = None
        new_item = None
        old_storage_section = None
        new_storage_section = None
        
        if 'item_id' in update_data:
            old_item = db.query(Item).filter(Item.id == db_entity.item_id).first()
            new_item = db.query(Item).filter(Item.id == update_data['item_id']).first()
            if not new_item:
                raise ValueError(f"Item '{update_data['item_id']}' not found")
            if new_item.item_type != expected_item_type:
                raise ValueError(f"Item '{update_data['item_id']}' must be of type {expected_item_type.value}, got {new_item.item_type.value}")
        
        if 'storage_section_id' in update_data:
            new_storage_section = db.query(StorageSection).filter(
                StorageSection.id == update_data['storage_section_id']
            ).first()
            if not new_storage_section:
                raise ValueError("Storage section not found")
            old_storage_section = db.query(StorageSection).filter(
                StorageSection.id == db_entity.storage_section_id
            ).first()
        
        if old_item is None:
            old_item = db.query(Item).filter(Item.id == db_entity.item_id).first()
        if new_item is None:
            new_item = old_item
        if old_storage_section is None:
            old_storage_section = db.query(StorageSection).filter(
                StorageSection.id == db_entity.storage_section_id
            ).first()
        if new_storage_section is None:
            new_storage_section = old_storage_section

        if (old_storage_section.id == new_storage_section.id and old_item.id != new_item.id):
            unit_difference = new_item.unit - old_item.unit
            projected_used_units = old_storage_section.used_units + unit_difference
            if projected_used_units > old_storage_section.total_units:
                available = old_storage_section.total_units - old_storage_section.used_units
                raise ValueError(
                    f"Storage section '{old_storage_section.id}' would exceed capacity. "
                    f"Available: {available}, Required: {unit_difference}"
                )
            old_storage_section.used_units += unit_difference

        elif old_storage_section.id != new_storage_section.id:
            projected_new_used_units = new_storage_section.used_units + new_item.unit
            if projected_new_used_units > new_storage_section.total_units:
                available = new_storage_section.total_units - new_storage_section.used_units
                raise ValueError(
                    f"Storage section '{new_storage_section.id}' would exceed capacity. "
                    f"Available: {available}, Required: {new_item.unit}"
                )
            old_storage_section.used_units -= old_item.unit
            new_storage_section.used_units += new_item.unit

        if 'rfid_tag_id' in update_data:
            if update_data['rfid_tag_id'] == db_entity.rfid_tag_id:
                pass
            else:
                old_rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == db_entity.rfid_tag_id).first()
                new_rfid_tag = db.query(RFIDTag).filter(RFIDTag.id == update_data['rfid_tag_id']).first()
                if not new_rfid_tag:
                    raise ValueError(f"RFID tag '{update_data['rfid_tag_id']}' not found")
                if new_rfid_tag.assigned == True:
                    raise ValueError(f"RFID tag '{update_data['rfid_tag_id']}' is already assigned to another entity")
                if old_rfid_tag:
                    old_rfid_tag.assigned = False
                new_rfid_tag.assigned = True
        
        if hasattr(db_entity, 'quantity') and hasattr(db_entity, 'capacity'):
            if 'quantity' in update_data and 'capacity' not in update_data:
                if update_data['quantity'] > db_entity.capacity:
                    raise ValueError(f"Quantity ({update_data['quantity']}) cannot exceed capacity ({db_entity.capacity})")
            if 'capacity' in update_data and 'quantity' not in update_data:
                if db_entity.quantity > update_data['capacity']:
                    raise ValueError(f"Current quantity ({db_entity.quantity}) exceeds new capacity ({update_data['capacity']})")
            if 'quantity' in update_data and 'capacity' in update_data:
                if update_data['quantity'] > update_data['capacity']:
                    raise ValueError(f"Quantity ({update_data['quantity']}) cannot exceed capacity ({update_data['capacity']})")
        
        for key, value in update_data.items():
            if hasattr(db_entity, key):
                setattr(db_entity, key, value)
        
        db.commit()
        db.refresh(db_entity)
        return db_entity
        
    except Exception as e:
        db.rollback()
        raise e