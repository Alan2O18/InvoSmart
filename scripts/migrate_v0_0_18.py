"""One-time migration for v0.0.18 schema/data normalization.

What this script does:
1) Adds new normalized Job columns if missing.
2) Copies `vlm_result_json` into `vlm_raw_json` when needed.
3) Backfills normalized fields from JSON (manual first, then VLM raw).
4) Rebuilds missing `invoice_items` rows from payload items.
5) Clears deprecated cache/blob columns (`manual_json_text`, `flattened_data`, `flattening_status`).

Usage:
    python scripts/migrate_v0_0_18.py
    python scripts/migrate_v0_0_18.py --db-path path/to/global.db
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.database.core import get_global_db_path

logger = logging.getLogger("migrate_v0_0_18")


@dataclass
class MigrationStats:
    jobs_scanned: int = 0
    jobs_backfilled: int = 0
    items_rebuilt_jobs: int = 0
    items_inserted: int = 0
    copied_vlm_raw_rows: int = 0


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _ensure_column(conn: sqlite3.Connection, table: str, column_name: str, ddl_type: str):
    cols = _table_columns(conn, table)
    if column_name in cols:
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_name} {ddl_type}")


def _parse_json(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _coerce_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except Exception:
        return None


def _extract_fields(payload: dict[str, Any]) -> dict[str, Any]:
    header = payload.get("header") if isinstance(payload.get("header"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

    voucher_id = (
        header.get("voucher_id")
        or header.get("invoice_id")
        or summary.get("voucher_id")
        or summary.get("invoice_id")
        or None
    )
    purpose = summary.get("purpose") or header.get("purpose") or None
    supplier = header.get("supplier") or summary.get("supplier") or None
    invoice_date = header.get("date") or summary.get("date") or None

    total_raw = summary.get("total")
    if total_raw in (None, ""):
        total_raw = header.get("total_amount")
    if total_raw in (None, ""):
        total_raw = header.get("total")

    return {
        "voucher_id": str(voucher_id).strip() if voucher_id not in (None, "") else None,
        "purpose": str(purpose).strip() if purpose not in (None, "") else None,
        "supplier": str(supplier).strip() if supplier not in (None, "") else None,
        "invoice_date": str(invoice_date).strip() if invoice_date not in (None, "") else None,
        "total_amount": _coerce_float(total_raw),
    }


def _iter_payload_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items = payload.get("items")
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        qty = item.get("qty")
        if qty in (None, ""):
            qty = item.get("quantity")
        out.append(
            {
                "category": item.get("category") or "未分類",
                "description": item.get("name") or item.get("description") or "",
                "quantity": _coerce_float(qty),
                "price": _coerce_float(item.get("price")),
                "total": _coerce_float(item.get("total")),
                "remark": item.get("remark") or "",
            }
        )
    return out


def _build_job_query(job_columns: set[str]) -> str:
    select_parts = ["job_id"]
    select_parts.append("manual_json_text" if "manual_json_text" in job_columns else "NULL AS manual_json_text")
    select_parts.append("vlm_raw_json" if "vlm_raw_json" in job_columns else "NULL AS vlm_raw_json")
    select_parts.append("vlm_result_json" if "vlm_result_json" in job_columns else "NULL AS vlm_result_json")
    return f"SELECT {', '.join(select_parts)} FROM jobs ORDER BY created_at ASC"


def _copy_vlm_raw(conn: sqlite3.Connection, job_columns: set[str]) -> int:
    if "vlm_raw_json" not in job_columns or "vlm_result_json" not in job_columns:
        return 0
    cursor = conn.execute(
        """
        UPDATE jobs
           SET vlm_raw_json = vlm_result_json
         WHERE (vlm_raw_json IS NULL OR TRIM(vlm_raw_json) = '')
           AND vlm_result_json IS NOT NULL
           AND TRIM(vlm_result_json) != ''
        """
    )
    return int(cursor.rowcount or 0)


def run_migration(db_path: Path) -> MigrationStats:
    stats = MigrationStats()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("BEGIN")

        _ensure_column(conn, "jobs", "vlm_raw_json", "TEXT")
        _ensure_column(conn, "jobs", "voucher_id", "TEXT")
        _ensure_column(conn, "jobs", "purpose", "TEXT")
        _ensure_column(conn, "jobs", "supplier", "TEXT")
        _ensure_column(conn, "jobs", "invoice_date", "TEXT")
        _ensure_column(conn, "jobs", "total_amount", "REAL")

        job_columns = _table_columns(conn, "jobs")
        stats.copied_vlm_raw_rows = _copy_vlm_raw(conn, job_columns)

        query = _build_job_query(job_columns)
        rows = conn.execute(query).fetchall()

        for row in rows:
            stats.jobs_scanned += 1
            job_id = str(row["job_id"])

            manual_payload = _parse_json(row["manual_json_text"])
            raw_payload = _parse_json(row["vlm_raw_json"])
            legacy_payload = _parse_json(row["vlm_result_json"])
            payload = manual_payload or raw_payload or legacy_payload
            if not payload:
                continue

            fields = _extract_fields(payload)
            conn.execute(
                """
                UPDATE jobs
                   SET voucher_id = ?,
                       purpose = ?,
                       supplier = ?,
                       invoice_date = ?,
                       total_amount = ?
                 WHERE job_id = ?
                """,
                (
                    fields["voucher_id"],
                    fields["purpose"],
                    fields["supplier"],
                    fields["invoice_date"],
                    fields["total_amount"],
                    job_id,
                ),
            )
            stats.jobs_backfilled += 1

            existing_count = conn.execute(
                "SELECT COUNT(1) FROM invoice_items WHERE job_id = ?",
                (job_id,),
            ).fetchone()[0]

            if int(existing_count or 0) == 0:
                items = _iter_payload_items(payload)
                if items:
                    stats.items_rebuilt_jobs += 1
                for item in items:
                    conn.execute(
                        """
                        INSERT INTO invoice_items
                            (job_id, category, description, quantity, price, total, remark)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job_id,
                            item["category"],
                            item["description"],
                            item["quantity"],
                            item["price"],
                            item["total"],
                            item["remark"],
                        ),
                    )
                    stats.items_inserted += 1

        if "manual_json_text" in job_columns:
            conn.execute("UPDATE jobs SET manual_json_text = NULL")
        if "flattened_data" in job_columns:
            conn.execute("UPDATE jobs SET flattened_data = NULL")
        if "flattening_status" in job_columns:
            conn.execute("UPDATE jobs SET flattening_status = NULL")

        conn.commit()
        return stats
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-time migration for v0.0.18")
    parser.add_argument("--db-path", default=None, help="Override global database path")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else get_global_db_path()
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        return 1

    logger.info("Running v0.0.18 migration on %s", db_path)
    stats = run_migration(db_path)

    logger.info("Migration completed")
    logger.info("jobs_scanned=%s", stats.jobs_scanned)
    logger.info("jobs_backfilled=%s", stats.jobs_backfilled)
    logger.info("copied_vlm_raw_rows=%s", stats.copied_vlm_raw_rows)
    logger.info("items_rebuilt_jobs=%s", stats.items_rebuilt_jobs)
    logger.info("items_inserted=%s", stats.items_inserted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
