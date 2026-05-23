# backend/repositories/job_repository.py
import json
import logging
import time
from typing import Optional, Dict, Any, List, Callable

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import Event, InvoiceItem, Job, Project

logger = logging.getLogger(__name__)


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


class JobRepository:
    """Data access layer for job persistence (VLM-First, Global DB)."""

    def __init__(self, project_id: str, session_factory: Callable[[], AsyncSession]):
        self.project_id = project_id
        self.session_factory = session_factory

    @staticmethod
    def _is_legacy_manual_payload(payload: dict[str, Any]) -> bool:
        """Heuristic: legacy payloads keep free-form header fields (e.g. buyer).

        v0.0.18 structured payloads usually include voucher/supplier/date or summary purpose/total.
        """
        header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        has_structured_header = any(
            header.get(key)
            for key in ("voucher_id", "invoice_id", "supplier", "date")
        )
        has_structured_summary = (
            summary.get("purpose") not in (None, "")
            or summary.get("total") not in (None, "")
        )
        return not (has_structured_header or has_structured_summary)

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
                    updated_at=now,
                )
                session.add(job)

            await session.commit()
            return job_id

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a job by ID (dictionary format with legacy keys preserved)."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return None

            vlm_payload = job.vlm_raw_json
            if vlm_payload in (None, ""):
                vlm_payload = getattr(job, "vlm_result_json", None)

            payload = {
                "project_id": job.project_id,
                "job_id": job.job_id,
                "image_path": job.image_path,
                "source_pdf_path": job.source_pdf_path,
                "compressed_pdf_path": job.compressed_pdf_path,
                "status": job.status,
                "pdf_status": job.pdf_status,
                "pdf_commands_json": job.pdf_commands_json,
                "vlm_raw_json": vlm_payload,
                # Legacy key kept for backward compatibility in callers/tests.
                "vlm_result_json": vlm_payload,
                "vlm_stats": job.vlm_stats,
                "validation_json": job.validation_json,
                "voucher_id": job.voucher_id,
                "purpose": job.purpose,
                "supplier": job.supplier,
                "invoice_date": job.invoice_date,
                "total_amount": job.total_amount,
                "qr_verified": job.qr_verified,
                "manual_updated_at": job.manual_updated_at,
                "source_format": job.source_format,
                "preview_cache_path": job.preview_cache_path,
                "manual_json_text": getattr(job, "manual_json_text", None),
                "flattened_data": None,
                "flattening_status": None,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
            }

            return payload

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID. Returns True if deleted."""
        async with self.session_factory() as session:
            stmt = delete(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0

    async def update_job(self, job_id: str, **fields) -> bool:
        """Update specific fields of a job with legacy key compatibility."""
        if not fields:
            return False

        fields.pop("flattened_data", None)
        fields.pop("flattening_status", None)

        alias_map = {}
        ignored_fields: set[str] = set()

        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return False

            for key, value in fields.items():
                if key == "vlm_result_json":
                    if hasattr(job, "vlm_raw_json"):
                        job.vlm_raw_json = value
                    if hasattr(job, "vlm_result_json"):
                        job.vlm_result_json = value
                    continue
                mapped = alias_map.get(key, key)
                if mapped in ignored_fields:
                    continue
                if hasattr(job, mapped):
                    setattr(job, mapped, value)

            job.updated_at = time.time()
            await session.commit()
            return True

    # ---------------------
    # Shared helpers
    # ---------------------
    async def _get_project_group(self, session: AsyncSession) -> str:
        stmt = select(Project.meta_data).where(Project.project_id == self.project_id)
        meta_data = (await session.execute(stmt)).scalar_one_or_none() or {}
        if isinstance(meta_data, dict):
            return str(meta_data.get("group") or "")
        return ""

    def _extract_header_fields(self, json_data: dict) -> dict[str, Any]:
        """Extract normalized Job columns from vlm/manual JSON payload."""
        header = json_data.get("header") if isinstance(json_data.get("header"), dict) else {}
        summary = json_data.get("summary") if isinstance(json_data.get("summary"), dict) else {}

        voucher_id = (
            header.get("voucher_id")
            or header.get("invoice_id")
            or summary.get("voucher_id")
            or summary.get("invoice_id")
            or ""
        )
        supplier = header.get("supplier") or summary.get("supplier") or ""
        invoice_date = header.get("date") or summary.get("date") or ""
        purpose = summary.get("purpose") or header.get("purpose") or ""

        total_raw = summary.get("total")
        if total_raw in (None, ""):
            total_raw = header.get("total_amount")
        if total_raw in (None, ""):
            total_raw = header.get("total")

        return {
            "voucher_id": str(voucher_id).strip() or None,
            "purpose": str(purpose).strip() or None,
            "supplier": str(supplier).strip() or None,
            "invoice_date": str(invoice_date).strip() or None,
            "total_amount": _coerce_float(total_raw),
        }

    @staticmethod
    def _invoice_item_to_payload(item: InvoiceItem) -> dict[str, Any]:
        return {
            "category": item.category or "未分類",
            "name": item.description or "",
            "description": item.description or "",
            "qty": item.quantity if item.quantity is not None else "",
            "quantity": item.quantity if item.quantity is not None else "",
            "price": item.price if item.price is not None else "",
            "total": item.total if item.total is not None else "",
            "remark": item.remark or "",
        }

    def _reconstruct_display_json(self, job: dict[str, Any], items: list[InvoiceItem]) -> dict[str, Any]:
        """Assemble frontend-compatible display JSON from DB fields + InvoiceItem rows."""
        header = {
            "voucher_id": job.get("voucher_id") or "",
            "invoice_id": job.get("voucher_id") or "",
            "supplier": job.get("supplier") or "",
            "date": job.get("invoice_date") or "",
        }
        summary = {
            "purpose": job.get("purpose") or "",
            "total": job.get("total_amount") if job.get("total_amount") is not None else "",
        }

        normalized_items = [self._invoice_item_to_payload(item) for item in items]

        raw_payload: dict[str, Any] = {}
        raw_vlm = job.get("vlm_result_json")
        if isinstance(raw_vlm, str) and raw_vlm.strip():
            try:
                parsed = json.loads(raw_vlm)
                raw_payload = parsed if isinstance(parsed, dict) else {}
            except Exception:
                raw_payload = {}

        raw_header = raw_payload.get("header") if isinstance(raw_payload.get("header"), dict) else {}
        raw_summary = raw_payload.get("summary") if isinstance(raw_payload.get("summary"), dict) else {}

        if not header["voucher_id"]:
            header["voucher_id"] = (
                raw_header.get("voucher_id")
                or raw_header.get("invoice_id")
                or raw_summary.get("voucher_id")
                or raw_summary.get("invoice_id")
                or ""
            )
            header["invoice_id"] = header["voucher_id"]
        if not header["supplier"]:
            header["supplier"] = raw_header.get("supplier") or raw_summary.get("supplier") or ""
        if not header["date"]:
            header["date"] = raw_header.get("date") or raw_summary.get("date") or ""
        if not summary["purpose"]:
            summary["purpose"] = raw_summary.get("purpose") or raw_header.get("purpose") or ""
        if summary["total"] in (None, ""):
            summary["total"] = (
                raw_summary.get("total")
                or raw_header.get("total_amount")
                or raw_header.get("total")
                or ""
            )

        if not normalized_items:
            raw_items = raw_payload.get("items") if isinstance(raw_payload.get("items"), list) else []
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                normalized_items.append(
                    {
                        "category": item.get("category") or "未分類",
                        "name": item.get("name") or item.get("description") or "",
                        "description": item.get("description") or item.get("name") or "",
                        "qty": item.get("qty") if item.get("qty") not in (None, "") else item.get("quantity", ""),
                        "quantity": item.get("quantity") if item.get("quantity") not in (None, "") else item.get("qty", ""),
                        "price": item.get("price", ""),
                        "total": item.get("total", ""),
                        "remark": item.get("remark") or "",
                    }
                )

        return {
            "header": header,
            "summary": summary,
            "items": normalized_items,
        }

    async def _sync_items_to_db(self, session: AsyncSession, job_id: str, json_data: dict):
        """Extract items from JSON and recreate InvoiceItem records in the same transaction."""
        items = json_data.get("items", [])
        if not isinstance(items, list):
            items = []

        await session.execute(delete(InvoiceItem).where(InvoiceItem.job_id == job_id))

        for item in items:
            if not isinstance(item, dict):
                continue

            qty_raw = item.get("qty")
            if qty_raw in (None, ""):
                qty_raw = item.get("quantity")
            qty = _coerce_float(qty_raw)

            price = _coerce_float(item.get("price"))
            total = _coerce_float(item.get("total"))

            session.add(
                InvoiceItem(
                    job_id=job_id,
                    category=str(item.get("category") or "未分類"),
                    description=str(item.get("name") or item.get("description") or ""),
                    quantity=qty,
                    price=price,
                    total=total,
                    remark=str(item.get("remark") or ""),
                )
            )

    async def delete_invoice_items(self, job_id: str) -> int:
        """Delete all InvoiceItem rows for a job in this project."""
        async with self.session_factory() as session:
            job_stmt = select(Job.job_id).where(Job.project_id == self.project_id, Job.job_id == job_id)
            exists = (await session.execute(job_stmt)).scalar_one_or_none()
            if not exists:
                return 0

            result = await session.execute(delete(InvoiceItem).where(InvoiceItem.job_id == job_id))
            await session.commit()
            return int(result.rowcount or 0)

    async def list_invoice_items(self, job_id: str) -> list[dict[str, Any]]:
        async with self.session_factory() as session:
            stmt = select(InvoiceItem).where(InvoiceItem.job_id == job_id).order_by(InvoiceItem.id.asc())
            rows = (await session.execute(stmt)).scalars().all()
            return [self._invoice_item_to_payload(row) for row in rows]

    async def list_invoice_items_for_jobs(self, job_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not job_ids:
            return {}

        async with self.session_factory() as session:
            stmt = (
                select(InvoiceItem)
                .where(InvoiceItem.job_id.in_(job_ids))
                .order_by(InvoiceItem.job_id.asc(), InvoiceItem.id.asc())
            )
            rows = (await session.execute(stmt)).scalars().all()

        grouped: dict[str, list[dict[str, Any]]] = {job_id: [] for job_id in job_ids}
        for row in rows:
            grouped.setdefault(row.job_id, []).append(self._invoice_item_to_payload(row))
        return grouped

    # ---------------------
    # VLM-First Specific
    # ---------------------
    async def complete_vlm(
        self,
        job_id: str,
        vlm_result: Dict[str, Any],
        validation: Dict[str, Any] = None,
        stats: Dict[str, Any] = None,
        qr_verified: bool = False,
    ) -> bool:
        """Complete VLM processing and sync normalized fields + items."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return False

            extracted = self._extract_header_fields(vlm_result if isinstance(vlm_result, dict) else {})

            job.status = "done"
            vlm_json_text = json.dumps(vlm_result, ensure_ascii=False)
            job.vlm_raw_json = vlm_json_text
            if hasattr(job, "vlm_result_json"):
                job.vlm_result_json = vlm_json_text
            job.validation_json = json.dumps(validation, ensure_ascii=False) if validation else None
            job.vlm_stats = json.dumps(stats, ensure_ascii=False) if stats else None
            job.qr_verified = 1 if qr_verified else 0
            job.voucher_id = extracted["voucher_id"]
            job.purpose = extracted["purpose"]
            job.supplier = extracted["supplier"]
            job.invoice_date = extracted["invoice_date"]
            job.total_amount = extracted["total_amount"]
            # New VLM result supersedes previous manual edits.
            if hasattr(job, "manual_json_text"):
                job.manual_json_text = None
            job.manual_updated_at = None
            job.updated_at = time.time()

            await self._sync_items_to_db(session, job_id, vlm_result if isinstance(vlm_result, dict) else {})

            session.add(
                Event(
                    job_id=job_id,
                    event_type="vlm_completed",
                    payload=json.dumps({"qr_verified": qr_verified}, ensure_ascii=False),
                )
            )

            await session.commit()
            return True

    async def save_manual_json(self, job_id: str, json_data: dict) -> bool:
        """Save manual JSON edits by updating normalized columns and InvoiceItems only."""
        async with self.session_factory() as session:
            stmt = select(Job).where(Job.project_id == self.project_id, Job.job_id == job_id)
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                return False

            payload = json_data if isinstance(json_data, dict) else {}
            extracted = self._extract_header_fields(payload)
            now = time.time()
            is_legacy_payload = self._is_legacy_manual_payload(payload)

            job.voucher_id = extracted["voucher_id"]
            job.purpose = extracted["purpose"]
            job.supplier = extracted["supplier"]
            job.invoice_date = extracted["invoice_date"]
            job.total_amount = extracted["total_amount"]
            if hasattr(job, "manual_json_text"):
                job.manual_json_text = json.dumps(payload, ensure_ascii=False) if is_legacy_payload else None
            job.manual_updated_at = now
            job.updated_at = now

            await self._sync_items_to_db(session, job_id, payload)

            session.add(
                Event(
                    job_id=job_id,
                    event_type="manual_json_saved",
                    payload=json.dumps({"timestamp": now}, ensure_ascii=False),
                )
            )

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
                    "source_pdf_path": j.source_pdf_path,
                    "status": j.status,
                    "pdf_status": j.pdf_status,
                    "voucher_id": j.voucher_id,
                    "supplier": j.supplier,
                    "invoice_date": j.invoice_date,
                    "total_amount": j.total_amount,
                    "manual_updated_at": j.manual_updated_at,
                    # Legacy compatibility field.
                    "flattening_status": None,
                    "created_at": j.created_at,
                    "updated_at": j.updated_at,
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
            stmt = (
                select(Job.job_id)
                .where(Job.project_id == self.project_id, Job.status.in_(["ready", "pending", "running"]))
                .limit(1)
            )
            result = (await session.execute(stmt)).scalar_one_or_none()
            return result is not None

    # ---------------------
    # Event Logging
    # ---------------------
    async def emit_event(self, job_id: str, event_type: str, payload_dict: Dict[str, Any]):
        """Append an event strictly related to this job."""
        async with self.session_factory() as session:
            session.add(
                Event(
                    job_id=job_id,
                    event_type=event_type,
                    payload=json.dumps(payload_dict, ensure_ascii=False),
                )
            )
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
                Job.status.in_(["pending", "running"]),
                Job.created_at < cutoff,
            )
            jobs = (await session.execute(stmt)).scalars().all()
            count = len(jobs)
            for job in jobs:
                job.status = "failed"
                job.updated_at = time.time()

            if count > 0:
                await session.commit()
            return count

    async def delete_all_project_jobs(self) -> int:
        """Delete all jobs and events for this project."""
        async with self.session_factory() as session:
            stmt = select(Job.job_id).where(Job.project_id == self.project_id)
            result = await session.execute(stmt)
            job_ids = [row[0] for row in result.fetchall()]

            if job_ids:
                await session.execute(delete(Event).where(Event.job_id.in_(job_ids)))

            result_del = await session.execute(delete(Job).where(Job.project_id == self.project_id))
            await session.commit()

            return int(result_del.rowcount or 0)

    # ---------------------
    # Presentation Helpers
    # ---------------------
    async def get_display_result(self, job_id: str) -> Optional[dict]:
        """Return frontend display JSON reconstructed from DB single-source-of-truth."""
        job = await self.get_job(job_id)
        if not job:
            return None

        async with self.session_factory() as session:
            stmt = select(InvoiceItem).where(InvoiceItem.job_id == job_id).order_by(InvoiceItem.id.asc())
            items = (await session.execute(stmt)).scalars().all()

        manual_json_text = job.get("manual_json_text")
        if isinstance(manual_json_text, str) and manual_json_text.strip():
            try:
                parsed_manual = json.loads(manual_json_text)
            except Exception:
                parsed_manual = None
            if isinstance(parsed_manual, dict):
                payload = dict(parsed_manual)
                payload["items"] = [self._invoice_item_to_payload(item) for item in items]
                return payload

        return self._reconstruct_display_json(job, items)

    async def get_job_details(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get full job details for editor view with backward-compatible fields."""
        job = await self.get_job(job_id)
        if not job:
            return None

        display_result = await self.get_display_result(job_id)

        validation = None
        vlm_stats = None
        try:
            if job.get("validation_json"):
                validation = json.loads(job.get("validation_json"))
        except Exception:
            validation = None
        try:
            if job.get("vlm_stats"):
                vlm_stats = json.loads(job.get("vlm_stats"))
        except Exception:
            vlm_stats = None

        manual_json_text = job.get("manual_json_text")
        if not manual_json_text and job.get("manual_updated_at") and isinstance(display_result, dict):
            manual_json_text = json.dumps(display_result, ensure_ascii=False)

        return {
            "job_id": job["job_id"],
            "image_path": job["image_path"],
            "source_pdf_path": job.get("source_pdf_path"),
            "compressed_pdf_path": job.get("compressed_pdf_path"),
            "status": job["status"],
            "pdf_status": job.get("pdf_status"),
            "vlm_result": display_result,
            "validation": validation,
            "vlm_stats": vlm_stats,
            "qr_verified": bool(job.get("qr_verified")),
            "manual_json_text": manual_json_text,
            # Deprecated fields retained for response shape compatibility.
            "flattened_data": None,
            "flattening_status": None,
            "manual_updated_at": job.get("manual_updated_at"),
            "created_at": job["created_at"],
            "updated_at": job["updated_at"],
        }
