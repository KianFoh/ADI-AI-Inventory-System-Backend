from sqlalchemy.orm import Session
from sqlalchemy import func, or_, case, Integer
from app.models.storage_section import StorageSection, SectionColor
from app.schemas.storage_section import StorageSectionCreate, StorageSectionUpdate
from typing import List, Optional, Tuple

def natural_sort_key_db(query):
    """Add natural sorting to SQLAlchemy query"""
    return query.order_by(
        # Sort by floor number (F1, F2, F10...)
        func.cast(func.substring(StorageSection.floor, 2), Integer),
        # Sort by cabinet number (C1, C2, C10...)
        func.cast(func.substring(StorageSection.cabinet, 2), Integer),
        # Sort by layer number (L1, L2, L10...)
        func.cast(func.substring(StorageSection.layer, 2), Integer),
        # Sort by color (RED, GREEN, BLUE, YELLOW)
        case(
            (StorageSection.color == SectionColor.RED, 1),
            (StorageSection.color == SectionColor.GREEN, 2),
            (StorageSection.color == SectionColor.BLUE, 3),
            (StorageSection.color == SectionColor.YELLOW, 4),
            else_=5
        )
    )

def get_storage_section(db: Session, section_id: str) -> Optional[StorageSection]:
    return db.query(StorageSection).filter(StorageSection.id == section_id).first()

def get_storage_sections(
    db: Session, 
    page: int = 1, 
    page_size: int = 10,
    search: Optional[str] = None,
    floor: Optional[str] = None,
    cabinet: Optional[str] = None,
    color: Optional[SectionColor] = None,
    show_full_only: Optional[bool] = None,
    show_empty_only: Optional[bool] = None
) -> Tuple[List[StorageSection], int]:
    """Get storage sections with pagination, search, and smart sorting"""
    query = db.query(StorageSection)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                StorageSection.id.ilike(search_term),
                StorageSection.floor.ilike(search_term),
                StorageSection.cabinet.ilike(search_term),
                StorageSection.layer.ilike(search_term)
            )
        )
    
    if floor:
        query = query.filter(StorageSection.floor == floor.upper())
    if cabinet:
        query = query.filter(StorageSection.cabinet == cabinet.upper())
    if color:
        query = query.filter(StorageSection.color == color)
    
    if show_full_only:
        query = query.filter(StorageSection.used_units >= StorageSection.total_units)
    if show_empty_only:
        query = query.filter(StorageSection.used_units == 0)
    
    query = natural_sort_key_db(query)
    total_count = query.count()
    
    skip = (page - 1) * page_size
    sections = query.offset(skip).limit(page_size).all()
    
    return sections, total_count

def create_storage_section(db: Session, section: StorageSectionCreate) -> StorageSection:
    section_id = StorageSection.generate_id(
        section.floor, section.cabinet, section.layer, section.color.value
    )
    
    db_section = StorageSection(
        id=section_id,
        **section.model_dump()
    )
    db.add(db_section)
    db.commit()
    db.refresh(db_section)
    return db_section

def update_storage_section(db: Session, section_id: str, section: StorageSectionUpdate) -> Optional[StorageSection]:
    db_section = db.query(StorageSection).filter(StorageSection.id == section_id).first()
    if db_section:
        update_data = section.model_dump(exclude_unset=True)
        
        if any(key in update_data for key in ['floor', 'cabinet', 'layer', 'color']):
            new_floor = update_data.get('floor', db_section.floor)
            new_cabinet = update_data.get('cabinet', db_section.cabinet)
            new_layer = update_data.get('layer', db_section.layer)
            new_color = update_data.get('color', db_section.color)
            
            new_id = StorageSection.generate_id(new_floor, new_cabinet, new_layer, new_color.value)
            update_data['id'] = new_id
        
        for key, value in update_data.items():
            setattr(db_section, key, value)
        db.commit()
        db.refresh(db_section)
    return db_section

def delete_storage_section(db: Session, section_id: str) -> Optional[StorageSection]:
    db_section = db.query(StorageSection).filter(StorageSection.id == section_id).first()
    if db_section:
        if db_section.used_units > 0:
            raise ValueError(f"Cannot delete storage section {section_id}. It contains {db_section.used_units} units of items.")
        
        db.delete(db_section)
        db.commit()
    return db_section

def search_storage_sections_by_keyword(db: Session, keyword: str, limit: int = 20) -> List[StorageSection]:
    search_term = f"%{keyword}%"
    query = db.query(StorageSection).filter(
        or_(
            StorageSection.id.ilike(search_term),
            StorageSection.floor.ilike(search_term),
            StorageSection.cabinet.ilike(search_term),
            StorageSection.layer.ilike(search_term)
        )
    )
    return natural_sort_key_db(query).limit(limit).all()

def get_sections_by_floor(db: Session, floor: str) -> List[StorageSection]:
    query = db.query(StorageSection).filter(StorageSection.floor == floor.upper())
    return natural_sort_key_db(query).all()

def get_sections_by_color(db: Session, color: SectionColor) -> List[StorageSection]:
    query = db.query(StorageSection).filter(StorageSection.color == color)
    return natural_sort_key_db(query).all()

def add_units_to_section(db: Session, section_id: str, units_to_add: int) -> Optional[StorageSection]:
    section = db.query(StorageSection).filter(StorageSection.id == section_id).first()
    if section:
        section.used_units += units_to_add
        db.commit()
        db.refresh(section)
    return section

def remove_units_from_section(db: Session, section_id: str, units_to_remove: int) -> Optional[StorageSection]:
    section = db.query(StorageSection).filter(StorageSection.id == section_id).first()
    if section:
        section.used_units = max(0, section.used_units - units_to_remove)
        db.commit()
        db.refresh(section)
    return section

def can_add_units_to_section(db: Session, section_id: str, units_needed: int) -> tuple[bool, str]:
    section = db.query(StorageSection).filter(StorageSection.id == section_id).first()
    if not section:
        return False, "Storage section not found"
    
    available_units = section.total_units - section.used_units
    if available_units < units_needed:
        return False, f"Not enough space. Available: {available_units}, Required: {units_needed}"
    
    return True, "Section has enough space"

def update_section_units(db: Session, old_section_id: str, new_section_id: str, units: int) -> None:
    if old_section_id:
        remove_units_from_section(db, old_section_id, units)
    if new_section_id:
        add_units_to_section(db, new_section_id, units)

def recalculate_section_used_units(db: Session, section_id: str) -> Optional[StorageSection]:
    from app.models.partition import Partition
    from app.models.large_item import LargeItem
    from app.models.item import Item
    
    # ✅ FIXED: Changed units_required to unit
    partition_units = db.query(func.coalesce(func.sum(Item.unit), 0)).join(
        Partition, Partition.item_id == Item.id
    ).filter(Partition.storage_section_id == section_id).scalar() or 0
    
    large_item_units = db.query(func.coalesce(func.sum(Item.unit), 0)).join(
        LargeItem, LargeItem.item_id == Item.id
    ).filter(LargeItem.storage_section_id == section_id).scalar() or 0
    
    total_used = partition_units + large_item_units
    
    section = db.query(StorageSection).filter(StorageSection.id == section_id).first()
    if section:
        section.used_units = total_used
        db.commit()
        db.refresh(section)
    
    return section

def get_sections_with_available_units(db: Session, min_units: int = 1) -> List[StorageSection]:
    query = db.query(StorageSection).filter(
        StorageSection.total_units - StorageSection.used_units >= min_units
    )
    return natural_sort_key_db(query).all()

def get_sections_by_utilization(db: Session, min_rate: float = 0.0, max_rate: float = 1.0) -> List[StorageSection]:
    sections = db.query(StorageSection).all()
    return [
        section for section in sections 
        if min_rate <= (section.used_units / section.total_units if section.total_units > 0 else 0) <= max_rate
    ]