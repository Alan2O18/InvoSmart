import sys
import json
import logging
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

import backend.database.core as db_core
from backend.database.models import Job, InvoiceItem

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_vlm_json")


async def migrate_data():
    db_core.init_db()
    
    try:
        async with db_core.AsyncSessionLocal() as session:
            # Load all jobs
            stmt = select(Job)
            result = await session.execute(stmt)
            jobs = result.scalars().all()
            
            migrated_jobs = 0
            migrated_items = 0
            
            for job in jobs:
                # Check if it already has items
                item_stmt = select(InvoiceItem).where(InvoiceItem.job_id == job.job_id)
                existing_items = (await session.execute(item_stmt)).scalars().all()
                if existing_items:
                    continue # Already migrated or has items
                    
                raw_json = job.manual_json_text or job.vlm_result_json
                if not raw_json:
                    continue
                    
                try:
                    data = json.loads(raw_json)
                    items = data.get("items", []) if isinstance(data, dict) else []
                except Exception as e:
                    logger.error(f"Failed to parse JSON for job {job.job_id}: {e}")
                    continue
                    
                if not isinstance(items, list):
                    logger.warning(f"'items' is not a list in job {job.job_id}")
                    continue
                    
                for item in items:
                    if not isinstance(item, dict):
                        continue
                        
                    # Map fields
                    category = item.get("category", "未分類") or "未分類"
                    name = item.get("name") or item.get("description", "")
                    
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
                    
                    invoice_item = InvoiceItem(
                        job_id=job.job_id,
                        category=str(category),
                        description=str(name),
                        quantity=qty,
                        price=price,
                        total=total,
                        remark=""
                    )
                    session.add(invoice_item)
                    migrated_items += 1
                    
                try:
                    await session.commit()
                    migrated_jobs += 1
                except Exception as e:
                    err_msg = getattr(e, 'orig', e)
                    logger.error(f"Commit failed for job {job.job_id}: {err_msg}")
                    with open("migration_errors.txt", "a", encoding="utf-8") as f:
                        f.write(f"Job {job.job_id} Error: {err_msg}\n")
                    await session.rollback()
                    
            logger.info(f"Migration complete: {migrated_jobs} jobs migrated, {migrated_items} items created.")
            
    except Exception as e:
        import traceback
        with open("migration_fatal.txt", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        logger.error(f"Fatal migration error: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_data())
