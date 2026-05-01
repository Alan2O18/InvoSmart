"""Tests for Person model and PersonRepository"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database.models import Person, Stamp
from backend.repositories.person_repository import PersonRepository
from backend.repositories.stamp_repository import StampRepository


@pytest.mark.asyncio
async def test_create_person(db_session: AsyncSession):
    """Test creating a new person."""
    repo = PersonRepository(db_session)
    
    person_data = await repo.create_person(
        name="John Doe",
        role="president",
        is_virtual=False
    )
    
    assert person_data["name"] == "John Doe"
    assert person_data["role"] == "president"
    assert person_data["is_virtual"] is False
    assert person_data["id"] is not None


@pytest.mark.asyncio
async def test_list_persons(db_session: AsyncSession):
    """Test listing all persons."""
    repo = PersonRepository(db_session)
    
    # Create test persons
    await repo.create_person("Person 1", "president", False)
    await repo.create_person("Person 2", "activity_general_affairs", False)
    
    persons = await repo.list_persons()
    assert len(persons) >= 2


@pytest.mark.asyncio
async def test_list_persons_by_role(db_session: AsyncSession):
    """Test listing persons by role."""
    repo = PersonRepository(db_session)
    
    # Create test persons
    await repo.create_person("President 1", "president", False)
    await repo.create_person("President 2", "president", False)
    await repo.create_person("Advisor 1", "advisor", False)
    
    presidents = await repo.list_persons_by_role("president")
    assert len(presidents) >= 2
    
    advisors = await repo.list_persons_by_role("advisor")
    assert len(advisors) >= 1


@pytest.mark.asyncio
async def test_get_person(db_session: AsyncSession):
    """Test getting a person by ID."""
    repo = PersonRepository(db_session)
    
    created = await repo.create_person("Test Person", "president", False)
    person_id = created["id"]
    
    retrieved = await repo.get_person(person_id)
    assert retrieved is not None
    assert retrieved["name"] == "Test Person"
    assert retrieved["role"] == "president"


@pytest.mark.asyncio
async def test_get_person_by_name(db_session: AsyncSession):
    """Test getting a person by name."""
    repo = PersonRepository(db_session)
    
    await repo.create_person("Unique Name", "president", False)
    
    person = await repo.get_person_by_name("Unique Name")
    assert person is not None
    assert person["role"] == "president"


@pytest.mark.asyncio
async def test_delete_person(db_session: AsyncSession):
    """Test deleting a person."""
    repo = PersonRepository(db_session)
    
    created = await repo.create_person("To Delete", "president", False)
    person_id = created["id"]
    
    # Delete the person
    success = await repo.delete_person(person_id)
    assert success is True
    
    # Verify it's deleted
    retrieved = await repo.get_person(person_id)
    assert retrieved is None


@pytest.mark.asyncio
async def test_ensure_virtual_persons(db_session: AsyncSession):
    """Test ensuring virtual persons exist."""
    repo = PersonRepository(db_session)
    
    result_ids = await repo.ensure_virtual_persons()
    
    assert "fin_original" in result_ids
    assert "fin_audited" in result_ids
    assert "club_seal" in result_ids
    
    # Call again and verify idempotency
    result_ids2 = await repo.ensure_virtual_persons()
    assert result_ids == result_ids2


@pytest.mark.asyncio
async def test_stamp_with_person_relationship(db_session: AsyncSession):
    """Test Stamp's relationship with Person."""
    person_repo = PersonRepository(db_session)
    stamp_repo = StampRepository(db_session)
    
    # Create a person
    person = await person_repo.create_person("Stamp Owner", "president", False)
    owner_id = person["id"]
    
    # Create stamps for this person
    from backend.database.models import Stamp as StampModel
    stamps = [
        StampModel(
            owner_id=owner_id,
            category="personal",
            image_path="path/to/stamp1.png",
        ),
        StampModel(
            owner_id=owner_id,
            category="personal",
            image_path="path/to/stamp2.png",
        ),
    ]
    
    created_stamps = await stamp_repo.create_stamps(stamps)
    assert len(created_stamps) == 2
    
    # List stamps by owner
    owner_stamps = await stamp_repo.list_stamps_by_owner(owner_id)
    assert len(owner_stamps) == 2
    assert all(s["owner_id"] == owner_id for s in owner_stamps)


@pytest.mark.asyncio
async def test_list_stamps_by_role(db_session: AsyncSession):
    """Test listing stamps by role (via Person)."""
    person_repo = PersonRepository(db_session)
    stamp_repo = StampRepository(db_session)
    
    # Create persons with specific roles
    president = await person_repo.create_person("President", "president", False)
    advisor = await person_repo.create_person("Advisor", "advisor", False)
    
    # Create stamps for each
    from backend.database.models import Stamp as StampModel
    
    president_stamps = [
        StampModel(
            owner_id=president["id"],
            category="personal",
            image_path="path/to/president_stamp.png",
        )
    ]
    
    advisor_stamps = [
        StampModel(
            owner_id=advisor["id"],
            category="personal",
            image_path="path/to/advisor_stamp.png",
        )
    ]
    
    await stamp_repo.create_stamps(president_stamps)
    await stamp_repo.create_stamps(advisor_stamps)
    
    # List stamps by role
    president_role_stamps = await stamp_repo.list_stamps_by_role("president")
    advisor_role_stamps = await stamp_repo.list_stamps_by_role("advisor")
    
    assert len(president_role_stamps) >= 1
    assert len(advisor_role_stamps) >= 1
