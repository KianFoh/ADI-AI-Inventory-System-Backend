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
    if not db_section:
        return None
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
    if not db_section:
        return None
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













