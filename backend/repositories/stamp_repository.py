from __future__ import annotations

from sqlalchemy import select, join
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Stamp, Person


class StampRepository:
    """CRUD repository for stamp records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dict(stamp: Stamp) -> dict:
        return {
            "id": stamp.id,
            "owner_id": stamp.owner_id,
            "category": stamp.category,
            "image_path": stamp.image_path,
            "created_at": stamp.created_at,
        }

    async def list_stamps(self) -> list[dict]:
        """List all stamps."""
        result = await self.session.execute(select(Stamp).order_by(Stamp.created_at.desc()))
        return [self._to_dict(row) for row in result.scalars().all()]

    async def list_stamps_by_owner(self, owner_id: int) -> list[dict]:
        """List stamps by owner (Person ID)."""
        result = await self.session.execute(
            select(Stamp).where(Stamp.owner_id == owner_id).order_by(Stamp.created_at.desc())
        )
        return [self._to_dict(row) for row in result.scalars().all()]

    async def list_stamps_by_role(self, role: str) -> list[dict]:
        """List stamps by owner's role (joins with Person table)."""
        result = await self.session.execute(
            select(Stamp).join(Person).where(Person.role == role).order_by(Stamp.created_at.desc())
        )
        return [self._to_dict(row) for row in result.scalars().all()]

    async def create_stamps(self, entities: list[Stamp]) -> list[dict]:
        """Create multiple stamps."""
        self.session.add_all(entities)
        await self.session.commit()
        for entity in entities:
            await self.session.refresh(entity)
        return [self._to_dict(entity) for entity in entities]

    async def get_stamp(self, stamp_id: int) -> dict | None:
        """Get a stamp by ID."""
        result = await self.session.execute(select(Stamp).where(Stamp.id == stamp_id))
        record = result.scalars().first()
        if record is None:
            return None
        return self._to_dict(record)

    async def delete_stamp(self, stamp_id: int) -> bool:
        """Delete a stamp by ID."""
        result = await self.session.execute(select(Stamp).where(Stamp.id == stamp_id))
        record = result.scalars().first()
        if record is None:
            return False

        await self.session.delete(record)
        await self.session.commit()
        return True
