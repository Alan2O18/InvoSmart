"""API Router for Person (人員和虛擬實體) management"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db
from backend.repositories.person_repository import PersonRepository

router = APIRouter()


class PersonCreate(BaseModel):
    name: str
    role: str
    is_virtual: bool = False


class PersonResponse(BaseModel):
    id: int
    name: str
    role: str
    is_virtual: bool
    created_at: float


def get_person_repo(db: AsyncSession = Depends(get_db)) -> PersonRepository:
    return PersonRepository(db)


@router.get("/persons", response_model=list[PersonResponse])
async def list_persons(repo: PersonRepository = Depends(get_person_repo)):
    """List all persons (real and virtual)."""
    rows = await repo.list_persons()
    return [PersonResponse(**row) for row in rows]


@router.get("/persons/by-role/{role}", response_model=list[PersonResponse])
async def list_persons_by_role(role: str, repo: PersonRepository = Depends(get_person_repo)):
    """List persons by role."""
    rows = await repo.list_persons_by_role(role)
    return [PersonResponse(**row) for row in rows]


@router.get("/persons/{person_id}", response_model=PersonResponse)
async def get_person(person_id: int, repo: PersonRepository = Depends(get_person_repo)):
    """Get a person by ID."""
    row = await repo.get_person(person_id)
    if not row:
        raise HTTPException(status_code=404, detail="Person not found")
    return PersonResponse(**row)


@router.post("/persons", response_model=PersonResponse)
async def create_person(
    data: PersonCreate, repo: PersonRepository = Depends(get_person_repo)
):
    """Create a new person."""
    # Check if person with same name already exists
    existing = await repo.get_person_by_name(data.name)
    if existing:
        raise HTTPException(status_code=409, detail="Person with this name already exists")
    
    row = await repo.create_person(data.name, data.role, data.is_virtual)
    return PersonResponse(**row)


@router.delete("/persons/{person_id}")
async def delete_person(person_id: int, repo: PersonRepository = Depends(get_person_repo)):
    """Delete a person by ID."""
    success = await repo.delete_person(person_id)
    if not success:
        raise HTTPException(status_code=404, detail="Person not found")
    return {"status": "deleted", "id": person_id}


@router.post("/persons/ensure-virtuals")
async def ensure_virtual_persons(repo: PersonRepository = Depends(get_person_repo)):
    """Ensure all virtual persons exist (called at system startup)."""
    result_ids = await repo.ensure_virtual_persons()
    return {"status": "ensured", "virtual_persons": result_ids}
