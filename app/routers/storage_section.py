from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import storage_section as section_crud
from app.models.storage_section import SectionColor, StorageSection
from app.models.container import Container
from app.models.partition import Partition
from app.models.large_item import LargeItem
from app.schemas.storage_section import (
    StorageSectionCreate, 
    StorageSectionUpdate, 
    StorageSectionResponse,
    PaginatedStorageSectionsResponse
)

router = APIRouter(
    prefix="/storage-sections",
    tags=["storage-sections"]
)

def is_section_referenced(db: Session, section_id: str) -> bool:
    return (
        db.query(Container).filter(Container.storage_section_id == section_id).first() or
        db.query(Partition).filter(Partition.storage_section_id == section_id).first() or
        db.query(LargeItem).filter(LargeItem.storage_section_id == section_id).first()
    )

@router.get("/", response_model=PaginatedStorageSectionsResponse)
def get_storage_sections(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Number of items per page"),
    search: Optional[str] = Query(None, description="Search in section components"),
    floor: Optional[str] = Query(None, description="Filter by floor (e.g., F1, F2)"),
    cabinet: Optional[str] = Query(None, description="Filter by cabinet (e.g., C1, C2)"),
    color: Optional[str] = Query(None, description="Filter by color"),
    db: Session = Depends(get_db)
):
    """Get storage sections with pagination, usage info, and smart sorting"""
    color_enum = None
    if color:
        try:
            color_enum = SectionColor(color.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"field": "color", "message": f"Invalid color. Must be one of: {[c.value for c in SectionColor]}"}
            )
    
    sections, total_count = section_crud.get_storage_sections(
        db, 
        page=page, 
        page_size=page_size, 
        search=search,
        floor=floor,
        cabinet=cabinet,
        color=color_enum
    )
    
    section_responses = [StorageSectionResponse.model_validate(section) for section in sections]
    
    return PaginatedStorageSectionsResponse.create(
        sections=section_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/search", response_model=List[StorageSectionResponse])
def search_storage_sections(
    q: str = Query(..., min_length=1, description="Search keyword"),
    limit: int = Query(20, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """Quick search storage sections for autocomplete/dropdown"""
    sections = section_crud.search_storage_sections_by_keyword(db, keyword=q, limit=limit)
    return [StorageSectionResponse.model_validate(section) for section in sections]

@router.get("/colors", response_model=List[str])
def get_available_colors():
    """Get list of available colors"""
    return [color.value for color in SectionColor]

@router.get("/floors/{floor}", response_model=List[StorageSectionResponse])
def get_sections_by_floor(floor: str, db: Session = Depends(get_db)):
    """Get all sections on a specific floor"""
    sections = section_crud.get_sections_by_floor(db, floor)
    return [StorageSectionResponse.model_validate(section) for section in sections]

@router.get("/colors/{color}", response_model=List[StorageSectionResponse])
def get_sections_by_color(
    color: str, 
    db: Session = Depends(get_db)
):
    """Get all sections by color"""
    try:
        color_enum = SectionColor(color.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"field": "color", "message": f"Invalid color. Must be one of: {[c.value for c in SectionColor]}"}
        )
    
    sections = section_crud.get_sections_by_color(db, color_enum)
    return [StorageSectionResponse.model_validate(section) for section in sections]

@router.get("/{section_id}", response_model=StorageSectionResponse)
def get_storage_section(section_id: str, db: Session = Depends(get_db)):
    """Get storage section by ID with usage information"""
    section = section_crud.get_storage_section(db, section_id=section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=[{"field": "section_id", "message": "Storage section not found"}]
        )
    return StorageSectionResponse.model_validate(section)

@router.post("/", response_model=StorageSectionResponse, status_code=status.HTTP_201_CREATED)
def create_storage_section(section: StorageSectionCreate, db: Session = Depends(get_db)):
    """Create new storage section"""
    section_id = StorageSection.generate_id(
        section.floor, section.cabinet, section.layer, section.color.value
    )
    if section_crud.get_storage_section(db, section_id=section_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=[{"field": "section_id", "message": "Storage section with this configuration already exists"}]
        )
    
    created_section = section_crud.create_storage_section(db=db, section=section)
    return StorageSectionResponse.model_validate(created_section)

@router.put("/{section_id}", response_model=StorageSectionResponse)
def update_storage_section(section_id: str, section: StorageSectionUpdate, db: Session = Depends(get_db)):
    """Update storage section"""
    # Generate the new ID from the updated attributes
    new_id = StorageSection.generate_id(
        section.floor, section.cabinet, section.layer, section.color.value
    )
    # If the new ID is different from the current and already exists, block update
    if new_id != section_id and section_crud.get_storage_section(db, section_id=new_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=[{"field": "section_id", "message": "Storage section with this configuration already exists"}]
        )
    try:
        updated_section = section_crud.update_storage_section(db, section_id=section_id, section=section)
        if not updated_section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=[{"field": "section_id", "message": "Storage section not found"}]
            )
        return StorageSectionResponse.model_validate(updated_section)
    except ValueError as e:
        err = e.args[0] if e.args and isinstance(e.args[0], dict) else {"field": "none", "message": str(e)}
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=[err]
        )

@router.delete("/{section_id}", response_model=StorageSectionResponse)
def delete_storage_section(section_id: str, db: Session = Depends(get_db)):
    if is_section_referenced(db, section_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=[{"field": "none", "message": "Cannot delete storage section: it is referenced by a container, partition, or large item."}]
        )
    deleted_section = section_crud.delete_storage_section(db, section_id=section_id)
    if not deleted_section:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=[{"field": "section_id", "message": "Storage section not found"}]
        )
    return StorageSectionResponse.model_validate(deleted_section)

@router.get("/count/total", response_model=int)
def get_section_count(db: Session = Depends(get_db)):
    """Get total section count"""
    return db.query(StorageSection).count()

