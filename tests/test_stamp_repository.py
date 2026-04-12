import time

import pytest

from backend.database.models import Stamp
from backend.repositories.stamp_repository import StampRepository


@pytest.mark.asyncio
async def test_stamp_repository_crud(async_session_factory):
    async with async_session_factory() as session:
        repo = StampRepository(session)

        created = await repo.create_stamps(
            [
                Stamp(
                    name="測試印章",
                    category="社團",
                    group_name="測試組",
                    image_path="backend/data/stamps/s1.png",
                    created_at=time.time(),
                )
            ]
        )

        assert len(created) == 1
        stamp_id = created[0]["id"]

        listed = await repo.list_stamps()
        assert len(listed) == 1
        assert listed[0]["name"] == "測試印章"

        fetched = await repo.get_stamp(stamp_id)
        assert fetched is not None
        assert fetched["category"] == "社團"

        deleted = await repo.delete_stamp(stamp_id)
        assert deleted is True

        gone = await repo.get_stamp(stamp_id)
        assert gone is None
