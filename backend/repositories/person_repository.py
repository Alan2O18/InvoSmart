from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Person


class PersonRepository:
    """CRUD repository for person records."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _to_dict(person: Person) -> dict:
        return {
            "id": person.id,
            "name": person.name,
            "role": person.role,
            "is_virtual": person.is_virtual,
            "created_at": person.created_at,
        }

    async def list_persons(self) -> list[dict]:
        """List all persons (real and virtual)."""
        result = await self.session.execute(select(Person).order_by(Person.name))
        return [self._to_dict(row) for row in result.scalars().all()]

    async def list_persons_by_role(self, role: str) -> list[dict]:
        """List persons by role."""
        result = await self.session.execute(select(Person).where(Person.role == role).order_by(Person.name))
        return [self._to_dict(row) for row in result.scalars().all()]

    async def get_person(self, person_id: int) -> dict | None:
        """Get a person by ID."""
        result = await self.session.execute(select(Person).where(Person.id == person_id))
        record = result.scalars().first()
        if record is None:
            return None
        return self._to_dict(record)

    async def get_person_by_name(self, name: str) -> dict | None:
        """Get a person by name."""
        result = await self.session.execute(select(Person).where(Person.name == name))
        record = result.scalars().first()
        if record is None:
            return None
        return self._to_dict(record)

    async def create_person(self, name: str, role: str, is_virtual: bool = False) -> dict:
        """Create a new person."""
        person = Person(name=name, role=role, is_virtual=is_virtual)
        self.session.add(person)
        await self.session.commit()
        await self.session.refresh(person)
        return self._to_dict(person)

    async def delete_person(self, person_id: int) -> bool:
        """Delete a person by ID."""
        result = await self.session.execute(select(Person).where(Person.id == person_id))
        person = result.scalars().first()
        if person is None:
            return False
        await self.session.delete(person)
        await self.session.commit()
        return True

    async def ensure_virtual_persons(self) -> dict[str, int]:
        """
        Ensure all virtual persons (金財務章、社團大章) exist.
        Returns a dict mapping role names to their IDs.
        """
        virtual_roles = [
            ("fin_original", "與正本相符"),
            ("fin_audited", "已稽核"),
            ("club_seal", "社團關防"),
        ]
        
        result_ids = {}
        for role, display_name in virtual_roles:
            # Check if virtual person already exists
            existing = await self.session.execute(
                select(Person).where((Person.role == role) & (Person.is_virtual == True))
            )
            existing_person = existing.scalars().first()
            
            if existing_person:
                result_ids[role] = existing_person.id
            else:
                # Create new virtual person
                new_person = Person(name=display_name, role=role, is_virtual=True)
                self.session.add(new_person)
                await self.session.commit()
                await self.session.refresh(new_person)
                result_ids[role] = new_person.id
        
        return result_ids
