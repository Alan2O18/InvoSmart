# backend/repositories/job_repository.py
import json
import time
import logging
from typing import Optional, Dict, Any, List, Callable

from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Job, Event, InvoiceItem

logger = logging.getLogger(__name__)

class JobRepository:
    """
    Data access layer for job persistence (VLM-First, Global DB).
    SQLAlchemy Async ORM version.
    """

    def __init__(self, project_id: str, session_factory: Callable[[], AsyncSession]):
        self.project_id = project_id
        self.session_factory = session_factory

    # ---------------------
    # CRUD Operations
    # ---------------------
    async def insert_job(self, job_id: str, image_path: str, status: str = "ready") -> str:
        """Insert or update a job record."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            
            now = time.time()
            if job:
                job.image_path = image_path
                job.status = status
                job.updated_at = now
            else:
                job = Job(
                    project_id=self.project_id,
                    job_id=job_id,
                    image_path=image_path,
                    status=status,
                    created_at=now,
                    updated_at=now
                )
                session.add(job)
            await session.commit()
            return job_id

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID (Dictionary format for legacy compatibility)."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return None
            return {
                "project_id": job.project_id,
                "job_id": job.job_id,
                "image_path": job.image_path,
                "source_pdf_path": job.source_pdf_path,
                "compressed_pdf_path": job.compressed_pdf_path,
                "status": job.status,
                "pdf_status": job.pdf_status,
                "pdf_commands_json": job.pdf_commands_json,
                "vlm_result_json": job.vlm_result_json,
                "vlm_stats": job.vlm_stats,
                "validation_json": job.validation_json,
                "qr_verified": job.qr_verified,
                "manual_json_text": job.manual_json_text,
                "manual_updated_at": job.manual_updated_at,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID. Returns True if deleted."""
        async with self.session_factory() as session:
            stmt = delete(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def update_job(self, job_id: str, **fields) -> bool:
        """Update specific fields of a job."""
        if not fields:
            return False
            
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return False
                
            for k, v in fields.items():
                if hasattr(job, k):
                    setattr(job, k, v)
            job.updated_at = time.time()
            await session.commit()
            return True

    # ---------------------
    # Database Sync Strategy
    # ---------------------
    async def _sync_items_to_db(self, session: AsyncSession, job_id: str, json_data: dict):
        """Extract items from JSON and recreate InvoiceItem records inside the SAME transaction."""
        items = json_data.get("items", [])
        if not items or not isinstance(items, list):
            items = []
            
        # Delete existing items for this job
        await session.execute(delete(InvoiceItem).where(InvoiceItem.job_id == job_id))
        
        # Insert new items
        for item in items:
            if not isinstance(item, dict):
                continue
                
            qty_raw = item.get("qty") or item.get("quantity", "")
            try:
                qty = float(qty_raw) if qty_raw not in (None, "") else None
            except ValueError:
                qty = None
                
            price_raw = item.get("price", "")
            try:
                price = float(price_raw) if price_raw not in (None, "") else None
            except ValueError:
                price = None
                
            total_raw = item.get("total", "")
            try:
                total = float(total_raw) if total_raw not in (None, "") else None
            except ValueError:
                total = None

            inv_item = InvoiceItem(
                job_id=job_id,
                category=str(item.get("category", "未分類") or "未分類"),
                description=str(item.get("name") or item.get("description", "")),
                quantity=qty,
                price=price,
                total=total,
                remark=""
            )
            session.add(inv_item)

    async def _stitch_items_from_db(self, job_id: str, base_json_str: Optional[str]) -> Optional[dict]:
        """Reconstruct the full JSON payload by overriding 'items' with true relational DB records."""
        if not base_json_str:
            return None
            
        try:
            payload = json.loads(base_json_str)
        except Exception:
            return None
            
        async with self.session_factory() as session:
            stmt = select(InvoiceItem).where(InvoiceItem.job_id == job_id).order_by(InvoiceItem.id)
            items_db = (await session.execute(stmt)).scalars().all()
            
            reconstructed_items = []
            for item in items_db:
                reconstructed_items.append({
                    "category": item.category,
                    "name": item.description,
                    "qty": item.quantity if item.quantity is not None else "",
                    "price": item.price if item.price is not None else "",
                    "total": item.total if item.total is not None else ""
                })
                
            payload["items"] = reconstructed_items
            return payload

    # ---------------------
    # VLM-First Specific
    # ---------------------
    async def complete_vlm(self, job_id: str, vlm_result: Dict[str, Any],
                     validation: Dict[str, Any] = None,
                     stats: Dict[str, Any] = None,
                     qr_verified: bool = False) -> bool:
        """Complete VLM processing, mark job done, and sync items to DB."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return False
                
            vlm_json = json.dumps(vlm_result, ensure_ascii=False)
            job.status = 'done'
            job.vlm_result_json = vlm_json
            job.validation_json = json.dumps(validation, ensure_ascii=False) if validation else None
            job.vlm_stats = json.dumps(stats, ensure_ascii=False) if stats else None
            job.qr_verified = 1 if qr_verified else 0
            job.updated_at = time.time()
            
            # Sync Items
            await self._sync_items_to_db(session, job_id, vlm_result)
            
            # Emit Event
            event = Event(
                job_id=job_id,
                event_type="vlm_completed",
                payload=json.dumps({"qr_verified": qr_verified}, ensure_ascii=False)
            )
            session.add(event)
            
            await session.commit()
            return True

    # ---------------------
    # Query Methods
    # ---------------------
    async def list_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all jobs for this project."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id).order_by(Job.created_at.asc())
            if status:
                stmt = stmt.where(Job.status == status)
                
            jobs = (await session.execute(stmt)).scalars().all()
            return [
                {
                    "project_id": j.project_id,
                    "job_id": j.job_id,
                    "image_path": j.image_path,
                    "source_pdf_path": j.source_pdf_path,  # Bug 2 fix: required for PDF filtering in frontend
                    "status": j.status,
                    "pdf_status": j.pdf_status,
                    "created_at": j.created_at,
                    "updated_at": j.updated_at,
                    # We usually don't need full JSONs in list endpoint (for optimization)
                }
                for j in jobs
            ]

    async def count_jobs(self) -> Dict[str, int]:
        """Count jobs grouped by status."""
        async with self.session_factory() as session:
            stmt = select(Job.status, func.count()).where(Job.project_id == self.project_id).group_by(Job.status)
            rows = (await session.execute(stmt)).all()
            return {status: count for status, count in rows}

    async def has_pending_work(self) -> bool:
        """Check if there's any pending or running work."""
        async with self.session_factory() as session:
            stmt = select(Job.job_id).where(
                Job.project_id == self.project_id,
                Job.status.in_(['ready', 'pending', 'running'])
            ).limit(1)
            result = (await session.execute(stmt)).scalar_one_or_none()
            return result is not None

    # ---------------------
    # Event Logging
    # ---------------------
    async def emit_event(self, job_id: str, event_type: str, payload_dict: Dict[str, Any]):
        """Append an event strictly related to this job."""
        import json
        async with self.session_factory() as session:
            new_event = Event(
                job_id=job_id,
                event_type=event_type,
                payload=json.dumps(payload_dict, ensure_ascii=False)
            )
            session.add(new_event)
            await session.commit()

    # ---------------------
    # Administrative Methods
    # ---------------------
    async def mark_stale_as_failed(self, stale_seconds: int = 60 * 60 * 6) -> int:
        """Mark pending/running jobs older than stale_seconds as failed."""
        cutoff = time.time() - stale_seconds
        async with self.session_factory() as session:
            stmt = select(Job).where(
                Job.project_id == self.project_id,
                Job.status.in_(['pending', 'running']),
                Job.created_at < cutoff
            )
            jobs = (await session.execute(stmt)).scalars().all()
            count = len(jobs)
            for j in jobs:
                j.status = 'failed'
                j.updated_at = time.time()
            
            if count > 0:
                await session.commit()
            return count

    async def delete_all_project_jobs(self) -> int:
        """Delete ALL jobs and events for this project."""
        async with self.session_factory() as session:
            # First, fetch all job IDs for this project
            stmt = select(Job.job_id).where(Job.project_id == self.project_id)
            result = await session.execute(stmt)
            job_ids = [row[0] for row in result.fetchall()]
            
            # Delete corresponding events
            if job_ids:
                from sqlalchemy import delete
                await session.execute(delete(Event).where(Event.job_id.in_(job_ids)))
                
            # Then delete the jobs
            stmt_del = delete(Job).where(Job.project_id == self.project_id)
            result_del = await session.execute(stmt_del)
            await session.commit()
            return result_del.rowcount

    # ---------------------
    # Presentation Helpers
    # ---------------------
    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full job details with STITCHED JSON (for editor view)."""
        job = await self.get_job(job_id)
        if not job:
            return None

        vlm_result = await self._stitch_items_from_db(job_id, job.get("vlm_result_json"))
        manual_json = await self._stitch_items_from_db(job_id, job.get("manual_json_text"))
        
        validation = None
        vlm_stats = None

        try:
            if job.get("validation_json"):
                validation = json.loads(job.get("validation_json"))
        except Exception:
            pass
        try:
            if job.get("vlm_stats"):
                vlm_stats = json.loads(job.get("vlm_stats"))
        except Exception:
            pass

        return {
            "job_id": job["job_id"],
            "image_path": job["image_path"],
            "source_pdf_path": job.get("source_pdf_path"),
            "compressed_pdf_path": job.get("compressed_pdf_path"),
            "status": job["status"],
            "pdf_status": job.get("pdf_status"),
            "vlm_result": vlm_result,
            "validation": validation,
            "vlm_stats": vlm_stats,
            "qr_verified": bool(job.get("qr_verified")),
            "manual_json_text": json.dumps(manual_json, ensure_ascii=False) if manual_json else None,
            "manual_updated_at": job.get("manual_updated_at"),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        }

    async def save_manual_json(self, job_id: str, json_data: dict) -> bool:
        """儲存人工編輯的 JSON 結果 (並同步 InvoiceItems 到關聯表)"""
        async with self.session_factory() as session:
            job = (await session.execute(select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id))).scalar_one_or_none()
            if not job:
                return False
                
            now = time.time()
            job.manual_json_text = json.dumps(json_data, ensure_ascii=False)
            job.manual_updated_at = now
            job.updated_at = now
            
            # Sync to actual relational table
            await self._sync_items_to_db(session, job_id, json_data)
            
            event = Event(
                job_id=job_id,
                event_type="manual_json_saved",
                payload=json.dumps({"timestamp": now}, ensure_ascii=False)
            )
            session.add(event)
            
            await session.commit()
            return True

    async def get_display_result(self, job_id: str) -> Optional[dict]:
        """獲取顯示用的結果 (包含關聯表重建的 items)"""
        job = await self.get_job(job_id)
        if not job:
            return None

        # Prefer manual over vlm
        base_json = job.get("manual_json_text") or job.get("vlm_result_json")
        if base_json:
            return await self._stitch_items_from_db(job_id, base_json)
            
        return None
