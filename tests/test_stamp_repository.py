import time

import pytest

from backend.database.models import Stamp, Person
from backend.repositories.stamp_repository import StampRepository


@pytest.mark.asyncio
async def test_stamp_repository_crud(async_session_factory):
    async with async_session_factory() as session:
        repo = StampRepository(session)
        
        # Create a Person first to satisfy FK constraint
        person = Person(name="測試印章", role="社團")
        session.add(person)
        await session.commit()
        await session.refresh(person)

        created = await repo.create_stamps(
            [
                Stamp(
                    owner_id=person.id,
                    image_path="backend/data/stamps/s1.png",
                    created_at=time.time(),
                )
            ]
        )

        assert len(created) == 1
        stamp_id = created[0]["id"]

        listed = await repo.list_stamps()
        assert len(listed) == 1
        assert listed[0]["owner_id"] == person.id

        fetched = await repo.get_stamp(stamp_id)
        assert fetched is not None
        assert fetched["owner_id"] == person.id

        deleted = await repo.delete_stamp(stamp_id)
        assert deleted is True

        gone = await repo.get_stamp(stamp_id)
        assert gone is None
