from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import partition as partition_crud
from app.models.partition import PartitionStatus
from app.schemas.partition import (
    PartitionCreate, 
    PartitionUpdate, 
    PartitionResponse,
    PaginatedPartitionsResponse
)

router = APIRouter(
    prefix="/partitions",
    tags=["partitions"]
)

@router.get("/", response_model=PaginatedPartitionsResponse)
def get_partitions(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    has_rfid: Optional[bool] = Query(None, description="Filter by RFID tag presence"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    """Get partitions with pagination"""
    status_enum = None
    if status:
        try:
            status_enum = PartitionStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in PartitionStatus]}"
            )
    
    partitions, total_count = partition_crud.get_partitions(
        db, page=page, page_size=page_size, search=search, has_rfid=has_rfid, status=status_enum
    )
    
    partition_responses = [PartitionResponse.model_validate(partition) for partition in partitions]
    
    return PaginatedPartitionsResponse.create(
        partitions=partition_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/statuses", response_model=List[str])
def get_partition_statuses():
    """Get available partition statuses"""
    return [status.value for status in PartitionStatus]

@router.get("/available", response_model=List[PartitionResponse])
def get_available_partitions(db: Session = Depends(get_db)):
    """Get all available partitions"""
    partitions = partition_crud.get_available_partitions(db)
    return [PartitionResponse.model_validate(partition) for partition in partitions]

@router.get("/status/{status}", response_model=List[PartitionResponse])
def get_partitions_by_status(status: str, db: Session = Depends(get_db)):
    """Get partitions by status"""
    try:
        status_enum = PartitionStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in PartitionStatus]}"
        )
    
    partitions = partition_crud.get_partitions_by_status(db, status_enum)
    return [PartitionResponse.model_validate(partition) for partition in partitions]

@router.get("/item/{item_id}", response_model=List[PartitionResponse])
def get_partitions_by_item(item_id: str, db: Session = Depends(get_db)):
    """Get all partitions for a specific item"""
    partitions = partition_crud.get_partitions_by_item(db, item_id)
    return [PartitionResponse.model_validate(partition) for partition in partitions]

@router.get("/storage-section/{storage_section_id}", response_model=List[PartitionResponse])
def get_partitions_by_storage_section(storage_section_id: str, db: Session = Depends(get_db)):
    """Get all partitions in a storage section"""
    partitions = partition_crud.get_partitions_by_storage_section(db, storage_section_id)
    return [PartitionResponse.model_validate(partition) for partition in partitions]

@router.get("/{partition_id}", response_model=PartitionResponse)
def get_partition(partition_id: str, db: Session = Depends(get_db)):
    """Get partition by ID"""
    partition = partition_crud.get_partition(db, partition_id=partition_id)
    if not partition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partition not found"
        )
    return PartitionResponse.model_validate(partition)

@router.post("/", response_model=PartitionResponse, status_code=status.HTTP_201_CREATED)
def create_partition(partition: PartitionCreate, db: Session = Depends(get_db)):
    """Create new partition with RFID automatically assigned"""
    try:
        created_partition = partition_crud.create_partition(db=db, partition=partition)
        return PartitionResponse.model_validate(created_partition)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{partition_id}", response_model=PartitionResponse)
def update_partition(partition_id: str, partition: PartitionUpdate, db: Session = Depends(get_db)):
    """Update partition (RFID cannot be changed)"""
    try:
        updated_partition = partition_crud.update_partition(db, partition_id=partition_id, partition=partition)
        if not updated_partition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partition not found"
            )
        return PartitionResponse.model_validate(updated_partition)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.patch("/{partition_id}/status", response_model=PartitionResponse)
def update_partition_status(
    partition_id: str, 
    new_status: str = Query(..., description="New status for the partition"),
    db: Session = Depends(get_db)
):
    """Update partition status"""
    try:
        status_enum = PartitionStatus(new_status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in PartitionStatus]}"
        )
    
    updated_partition = partition_crud.update_partition_status(db, partition_id, status_enum)
    if not updated_partition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partition not found"
        )
    return PartitionResponse.model_validate(updated_partition)

@router.patch("/{partition_id}/quantity", response_model=PartitionResponse)
def update_partition_quantity(
    partition_id: str, 
    quantity: int = Query(..., ge=0, description="New quantity"),
    db: Session = Depends(get_db)
):
    """Update partition quantity"""
    try:
        updated_partition = partition_crud.update_partition_quantity(db, partition_id, quantity)
        if not updated_partition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Partition not found"
            )
        return PartitionResponse.model_validate(updated_partition)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{partition_id}", response_model=PartitionResponse)
def delete_partition(partition_id: str, db: Session = Depends(get_db)):
    """Delete partition (RFID automatically unassigned)"""
    deleted_partition = partition_crud.delete_partition(db, partition_id=partition_id)
    if not deleted_partition:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Partition not found"
        )
    return PartitionResponse.model_validate(deleted_partition)

@router.get("/count/total", response_model=int)
def get_partition_count(db: Session = Depends(get_db)):
    """Get total partition count"""
    return partition_crud.get_partition_count(db)

@router.get("/count/status/{status}", response_model=int)
def get_partition_count_by_status(status: str, db: Session = Depends(get_db)):
    """Get partition count by status"""
    try:
        status_enum = PartitionStatus(status.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {[s.value for s in PartitionStatus]}"
        )
    
    return partition_crud.get_partition_count_by_status(db, status_enum)