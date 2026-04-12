from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Stamp


class StampRepository:
    """CRUD repository for stamp records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dict(stamp: Stamp) -> dict:
        return {
            "id": stamp.id,
            "name": stamp.name,
            "category": stamp.category,
            "group_name": stamp.group_name,
            "image_path": stamp.image_path,
            "created_at": stamp.created_at,
        }

    async def list_stamps(self) -> list[dict]:
        result = await self.session.execute(select(Stamp).order_by(Stamp.created_at.desc()))
        return [self._to_dict(row) for row in result.scalars().all()]

    async def create_stamps(self, entities: list[Stamp]) -> list[dict]:
        self.session.add_all(entities)
        await self.session.commit()
        for entity in entities:
            await self.session.refresh(entity)
        return [self._to_dict(entity) for entity in entities]

    async def get_stamp(self, stamp_id: int) -> dict | None:
        result = await self.session.execute(select(Stamp).where(Stamp.id == stamp_id))
        record = result.scalars().first()
        if record is None:
            return None
        return self._to_dict(record)

    async def delete_stamp(self, stamp_id: int) -> bool:
        result = await self.session.execute(select(Stamp).where(Stamp.id == stamp_id))
        record = result.scalars().first()
        if record is None:
            return False

        await self.session.delete(record)
        await self.session.commit()
        return True
