from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.crud import container as container_crud
from app.models.container import ContainerStatus
from app.schemas.container import (
    ContainerCreate,
    ContainerUpdate,
    ContainerResponse,
    PaginatedContainersResponse
)

router = APIRouter(
    prefix="/containers",
    tags=["containers"]
)

@router.get("/", response_model=PaginatedContainersResponse)
def get_containers(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_db)
):
    status_enum = None
    if status:
        try:
            status_enum = ContainerStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Must be one of: {[s.value for s in ContainerStatus]}"
            )
    containers, total_count = container_crud.get_containers(
        db, page=page, page_size=page_size, search=search, status=status_enum
    )
    container_responses = [ContainerResponse.model_validate(container) for container in containers]
    return PaginatedContainersResponse.create(
        containers=container_responses,
        total_count=total_count,
        page=page,
        page_size=page_size
    )

@router.get("/statuses", response_model=List[str])
def get_container_statuses():
    return [status.value for status in ContainerStatus]

@router.get("/item/{item_id}", response_model=List[ContainerResponse])
def get_containers_by_item(item_id: str, db: Session = Depends(get_db)):
    containers = container_crud.get_containers_by_item(db, item_id)
    return [ContainerResponse.model_validate(container) for container in containers]

@router.get("/storage-section/{storage_section_id}", response_model=List[ContainerResponse])
def get_containers_by_storage_section(storage_section_id: str, db: Session = Depends(get_db)):
    containers = container_crud.get_containers_by_storage_section(db, storage_section_id)
    return [ContainerResponse.model_validate(container) for container in containers]

@router.get("/count", response_model=int)
def get_container_count(db: Session = Depends(get_db)):
    return container_crud.get_container_count(db)

@router.get("/{container_id}", response_model=ContainerResponse)
def get_container(container_id: str, db: Session = Depends(get_db)):
    container = container_crud.get_container(db, container_id=container_id)
    if not container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found"
        )
    return ContainerResponse.model_validate(container)

@router.post("/", response_model=ContainerResponse, status_code=status.HTTP_201_CREATED)
def create_container(container: ContainerCreate, db: Session = Depends(get_db)):
    try:
        created_container = container_crud.create_container(db=db, container=container)
        return ContainerResponse.model_validate(created_container)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/{container_id}", response_model=ContainerResponse)
def update_container(container_id: str, container: ContainerUpdate, db: Session = Depends(get_db)):
    try:
        updated_container = container_crud.update_container(db, container_id=container_id, container=container)
        if not updated_container:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Container not found"
            )
        return ContainerResponse.model_validate(updated_container)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/{container_id}", response_model=ContainerResponse)
def delete_container(container_id: str, db: Session = Depends(get_db)):
    deleted_container = container_crud.delete_container(db, container_id=container_id)
    if not deleted_container:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Container not found"
        )
    return ContainerResponse.model_validate(deleted_container)