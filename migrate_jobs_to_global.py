#!/usr/bin/env python3
"""
一次性遷移腳本：將所有專案的 jobs.db 資料遷移至全域 global.db
Migration Script: Move all per-project jobs.db data into global.db

使用方式 (Usage):
    micromamba run -n OCR_GA python migrate_jobs_to_global.py

功能：
    1. 掃描 workspace 下所有含 jobs.db 的專案資料夾
    2. 讀取每個 jobs.db 裡的 jobs 和 events 表格
    3. 加上 project_id 標籤後，INSERT 進 global.db
    4. 將舊的 jobs.db 重新命名為 jobs.db.bak (安全回退)
"""
import sqlite3
import os
import sys
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_jobs")

# 路徑設定
BACKEND_DIR = Path(__file__).parent / "backend"
DATA_DIR = BACKEND_DIR / "data"
GLOBAL_DB = DATA_DIR / "global.db"

# 從 config.json 或環境推斷 workspace root
def get_workspace_root() -> Path:
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        ws = cfg.get("project_manager_settings", {}).get("workspace_root", "")
        if ws:
            return Path(ws)
    # fallback: 常見的預設位置
    return DATA_DIR / "projects"


def init_global_schema(conn: sqlite3.Connection):
    """確保 global.db 具備新版的 jobs + events 表格 (含 project_id)"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            project_id TEXT NOT NULL,
            job_id TEXT NOT NULL,
            image_path TEXT NOT NULL,
            status TEXT NOT NULL,
            vlm_result_json TEXT,
            vlm_stats TEXT,
            validation_json TEXT,
            qr_verified INTEGER DEFAULT 0,
            manual_json_text TEXT,
            manual_updated_at REAL,
            created_at REAL DEFAULT (strftime('%s','now')),
            updated_at REAL DEFAULT (strftime('%s','now')),
            PRIMARY KEY (project_id, job_id)
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(project_id, status);
        
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            job_id TEXT,
            event_type TEXT,
            ts REAL DEFAULT (strftime('%s','now')),
            payload TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_job ON events(project_id, job_id);
    """)
    conn.commit()


def migrate_project(global_conn: sqlite3.Connection, project_id: str, jobs_db_path: Path) -> dict:
    """遷移單一專案的 jobs.db 至 global.db"""
    stats = {"jobs": 0, "events": 0, "skipped": 0}
    
    try:
        proj_conn = sqlite3.connect(str(jobs_db_path), timeout=10)
        proj_conn.row_factory = sqlite3.Row
    except Exception as e:
        logger.error(f"  無法開啟 {jobs_db_path}: {e}")
        return stats

    try:
        cur = proj_conn.cursor()
        
        # --- 遷移 jobs ---
        try:
            cur.execute("SELECT * FROM jobs")
            rows = cur.fetchall()
        except sqlite3.OperationalError:
            logger.warning(f"  {project_id}: jobs 表不存在，跳過")
            rows = []
        
        for row in rows:
            d = dict(row)
            job_id = d.get("job_id", "")
            
            try:
                global_conn.execute(
                    """INSERT OR IGNORE INTO jobs 
                       (project_id, job_id, image_path, status, vlm_result_json, vlm_stats, 
                        validation_json, qr_verified, manual_json_text, manual_updated_at,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        job_id,
                        d.get("image_path", ""),
                        d.get("status", "ready"),
                        d.get("vlm_result_json"),
                        d.get("vlm_stats"),
                        d.get("validation_json"),
                        d.get("qr_verified", 0),
                        d.get("manual_json_text"),
                        d.get("manual_updated_at"),
                        d.get("created_at"),
                        d.get("updated_at"),
                    )
                )
                stats["jobs"] += 1
            except sqlite3.IntegrityError:
                stats["skipped"] += 1  # 已存在，跳過
            except Exception as e:
                logger.warning(f"  遷移 job {job_id} 失敗: {e}")

        # --- 遷移 events ---
        try:
            cur.execute("SELECT * FROM events")
            event_rows = cur.fetchall()
        except sqlite3.OperationalError:
            logger.warning(f"  {project_id}: events 表不存在，跳過")
            event_rows = []

        for row in event_rows:
            d = dict(row)
            try:
                global_conn.execute(
                    """INSERT INTO events (project_id, job_id, event_type, ts, payload)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        project_id,
                        d.get("job_id"),
                        d.get("event_type"),
                        d.get("ts"),
                        d.get("payload"),
                    )
                )
                stats["events"] += 1
            except Exception as e:
                logger.warning(f"  遷移 event 失敗: {e}")
        
        global_conn.commit()

    finally:
        proj_conn.close()

    return stats


def main():
    workspace = get_workspace_root()
    logger.info(f"=== Jobs Migration Script ===")
    logger.info(f"Workspace: {workspace}")
    logger.info(f"Global DB: {GLOBAL_DB}")

    if not workspace.exists():
        logger.warning(f"Workspace 目錄不存在: {workspace}")
        logger.info("沒有需要遷移的資料。")
        return

    # 連接 global.db 並確保 schema
    GLOBAL_DB.parent.mkdir(parents=True, exist_ok=True)
    global_conn = sqlite3.connect(str(GLOBAL_DB), timeout=30)
    global_conn.execute("PRAGMA journal_mode=WAL;")
    global_conn.execute("PRAGMA synchronous=NORMAL;")
    init_global_schema(global_conn)

    # 掃描所有專案
    total_stats = {"projects": 0, "jobs": 0, "events": 0, "skipped": 0, "backed_up": 0}

    for entry in sorted(workspace.iterdir()):
        if not entry.is_dir():
            continue
        jobs_db = entry / "jobs.db"
        if not jobs_db.exists():
            continue

        project_id = entry.name
        logger.info(f"遷移專案: {project_id}")
        
        stats = migrate_project(global_conn, project_id, jobs_db)
        total_stats["projects"] += 1
        total_stats["jobs"] += stats["jobs"]
        total_stats["events"] += stats["events"]
        total_stats["skipped"] += stats["skipped"]

        logger.info(f"  -> jobs: {stats['jobs']}, events: {stats['events']}, skipped: {stats['skipped']}")

        # 備份舊的 jobs.db -> jobs.db.bak
        bak_path = jobs_db.with_suffix(".db.bak")
        try:
            if bak_path.exists():
                bak_path.unlink()  # 移除舊備份
            jobs_db.rename(bak_path)
            total_stats["backed_up"] += 1
            logger.info(f"  -> 已備份: {bak_path}")
        except Exception as e:
            logger.warning(f"  -> 備份失敗 (不影響遷移): {e}")

    global_conn.close()

    logger.info("=== 遷移完成 ===")
    logger.info(f"  專案數: {total_stats['projects']}")
    logger.info(f"  Jobs 遷移: {total_stats['jobs']}")
    logger.info(f"  Events 遷移: {total_stats['events']}")
    logger.info(f"  已跳過 (重複): {total_stats['skipped']}")
    logger.info(f"  已備份: {total_stats['backed_up']} 個 jobs.db -> jobs.db.bak")


if __name__ == "__main__":
    main()
