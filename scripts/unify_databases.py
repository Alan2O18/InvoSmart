#!/usr/bin/env python3
"""
Phase 4 Unification Script: 清理並統一所有 SQLite 資料庫到單一 global.db

執行步驟：
  A. 封存舊的混亂 DB (backend/data/global.db, workspace/global.db) → .bak
  B. 從 global_projects.db 轉移 projects / groups / vocabulary
  C. 從各專案的 jobs.db.bak 找回真實的 jobs / events（跳過被測試汙染的 DB）
  D. 封存 global_projects.db → .bak

用法：
    micromamba run -n OCR_GA python scripts/unify_databases.py
"""
import sqlite3
import json
import os
import sys
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("unify_db")

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

# ── 讀取 config.json ───────────────────────────────────────────────────────────
with open(CONFIG_PATH, encoding="utf-8") as f:
    cfg = json.load(f)

pms = cfg["project_manager_settings"]
WORKSPACE_ROOT = Path(pms["workspace_root"]).expanduser().resolve()
OLD_PROJECTS_DB = Path(pms["global_db_path"]).expanduser().resolve()

# 被汙染的舊 DB（測試垃圾）
LEGACY_GLOBAL_DBS = [
    ROOT / "backend" / "data" / "global.db",
    WORKSPACE_ROOT / "global.db",
]

# 唯一標準 DB（輸出）
UNIFIED_DB = Path(pms["global_db_path"]).expanduser().resolve()

# ── Schema SQL ────────────────────────────────────────────────────────────────
SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT,
  root_path TEXT,
  status TEXT,
  created_at REAL,
  updated_at REAL,
  notes TEXT,
  metadata TEXT
);

CREATE TABLE IF NOT EXISTS groups (
  group_name TEXT PRIMARY KEY,
  leader_name TEXT
);

CREATE TABLE IF NOT EXISTS vocabulary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT,
  term TEXT,
  frequency INTEGER DEFAULT 1,
  last_used_at REAL,
  UNIQUE(category, term)
);

CREATE TABLE IF NOT EXISTS suggestions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT NOT NULL,
  value TEXT NOT NULL,
  count INTEGER DEFAULT 1,
  last_used_at REAL,
  UNIQUE(category, value)
);

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
"""

def backup(path: Path):
    """Rename path → path.bak (overwrites existing .bak)"""
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        if bak.exists():
            bak.unlink()
        shutil.move(str(path), str(bak))
        log.info(f"  封存: {path.name} → {bak.name}")

def open_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ════════════════════════════════════════════════════════════════════════════════
def step_a_backup_legacy():
    """A. 封存舊的混亂 DB"""
    log.info("=== 步驟 A: 封存被汙染的舊 DB ===")
    for p in LEGACY_GLOBAL_DBS:
        # If the "legacy" path IS the target UNIFIED_DB path, skip it
        if p.resolve() == UNIFIED_DB.resolve():
            log.info(f"  跳過（即為目標 DB）: {p}")
            continue
        backup(p)


def step_b_migrate_projects():
    """B. 從 global_projects.db 轉移 projects / groups / vocabulary"""
    log.info("=== 步驟 B: 轉移 projects / groups / vocabulary ===")
    if not OLD_PROJECTS_DB.exists():
        log.warning(f"  找不到 {OLD_PROJECTS_DB}，跳過")
        return

    src = open_db(OLD_PROJECTS_DB)
    dst = open_db(UNIFIED_DB)
    stats = {"projects": 0, "groups": 0, "vocabulary": 0}

    # projects
    for row in src.execute("SELECT * FROM projects"):
        d = dict(row)
        dst.execute(
            "INSERT OR REPLACE INTO projects (project_id,name,root_path,status,created_at,updated_at,notes,metadata) VALUES (?,?,?,?,?,?,?,?)",
            (d["project_id"], d.get("name"), d.get("root_path"), d.get("status"),
             d.get("created_at"), d.get("updated_at"), d.get("notes"), d.get("metadata")),
        )
        stats["projects"] += 1

    # groups
    try:
        for row in src.execute("SELECT * FROM groups"):
            d = dict(row)
            dst.execute("INSERT OR REPLACE INTO groups VALUES (?,?)", (d["group_name"], d.get("leader_name")))
            stats["groups"] += 1
    except sqlite3.OperationalError:
        pass  # table may not exist

    # vocabulary
    try:
        for row in src.execute("SELECT * FROM vocabulary"):
            d = dict(row)
            dst.execute(
                "INSERT OR IGNORE INTO vocabulary (category,term,frequency,last_used_at) VALUES (?,?,?,?)",
                (d.get("category"), d.get("term"), d.get("frequency", 1), d.get("last_used_at")),
            )
            stats["vocabulary"] += 1
    except sqlite3.OperationalError:
        pass

    dst.commit()
    src.close()
    dst.close()
    log.info(f"  projects: {stats['projects']}, groups: {stats['groups']}, vocabulary: {stats['vocabulary']}")


def step_c_migrate_jobs():
    """C. 從各專案 jobs.db.bak 找回乾淨的 jobs/events"""
    log.info("=== 步驟 C: 從 jobs.db.bak 找回真實 Jobs ===")
    dst = open_db(UNIFIED_DB)
    total = {"jobs": 0, "events": 0}

    # 只掃描上層 REAL_PROJECTS（跳過隱藏目錄、backend、frontend...）
    skip_dirs = {"backend", "frontend", ".git", "tests", "docs", "dev_data", "logs", "scripts",
                 ".vscode", ".pytest_cache", "htmlcov", "__pycache__", ".agent"}

    for entry in sorted(WORKSPACE_ROOT.iterdir()):
        if not entry.is_dir() or entry.name in skip_dirs:
            continue

        bak_path = entry / "jobs.db.bak"
        if not bak_path.exists():
            continue

        project_id = entry.name
        log.info(f"  讀取: {project_id}/jobs.db.bak")
        try:
            src = sqlite3.connect(str(bak_path), timeout=10)
            src.row_factory = sqlite3.Row

            # jobs
            try:
                for row in src.execute("SELECT * FROM jobs"):
                    d = dict(row)
                    job_id = d.get("job_id", "")
                    try:
                        dst.execute(
                            """INSERT OR IGNORE INTO jobs
                               (project_id,job_id,image_path,status,vlm_result_json,
                                vlm_stats,validation_json,qr_verified,manual_json_text,
                                manual_updated_at,created_at,updated_at)
                               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (project_id, job_id,
                             d.get("image_path",""), d.get("status","pending"),
                             d.get("vlm_result_json"), d.get("vlm_stats"),
                             d.get("validation_json"), d.get("qr_verified", 0),
                             d.get("manual_json_text"), d.get("manual_updated_at"),
                             d.get("created_at"), d.get("updated_at")),
                        )
                        total["jobs"] += 1
                    except Exception as e:
                        log.warning(f"    job {job_id} 插入失敗: {e}")
            except sqlite3.OperationalError as e:
                log.warning(f"    jobs 表不存在: {e}")

            # events
            try:
                for row in src.execute("SELECT * FROM events"):
                    d = dict(row)
                    try:
                        dst.execute(
                            "INSERT INTO events (project_id,job_id,event_type,ts,payload) VALUES (?,?,?,?,?)",
                            (project_id, d.get("job_id"), d.get("event_type"), d.get("ts"), d.get("payload")),
                        )
                        total["events"] += 1
                    except Exception as e:
                        log.warning(f"    event 插入失敗: {e}")
            except sqlite3.OperationalError:
                pass

            src.close()
        except Exception as e:
            log.error(f"  無法開啟 {bak_path}: {e}")

    dst.commit()
    dst.close()
    log.info(f"  jobs: {total['jobs']}, events: {total['events']}")


def step_d_backup_old_projects_db():
    """D. 封存 global_projects.db"""
    log.info("=== 步驟 D: 封存 global_projects.db ===")
    backup(OLD_PROJECTS_DB)


def main():
    log.info(f"Workspace root: {WORKSPACE_ROOT}")
    log.info(f"Unified DB target: {UNIFIED_DB}")

    # 確保目標的父目錄存在
    UNIFIED_DB.parent.mkdir(parents=True, exist_ok=True)

    # 若 UNIFIED_DB 已存在且不是舊的 legacy db 之一，先備份目標再重建
    if UNIFIED_DB.exists():
        is_legacy = any(p.resolve() == UNIFIED_DB.resolve() for p in LEGACY_GLOBAL_DBS)
        if is_legacy:
            # 會在 step_a 中被封存
            pass
        else:
            log.warning(f"目標 {UNIFIED_DB} 已存在，先備份再重建")
            backup(UNIFIED_DB)

    step_a_backup_legacy()

    # 建立乾淨的目標 DB 並初始化 schema
    conn = sqlite3.connect(str(UNIFIED_DB), timeout=30)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    log.info(f"已建立乾淨的統一 DB: {UNIFIED_DB}")

    step_b_migrate_projects()
    step_c_migrate_jobs()
    step_d_backup_old_projects_db()

    log.info("=== 🎉 資料庫統一完成！ ===")
    log.info(f"所有資料現已集中於: {UNIFIED_DB}")


if __name__ == "__main__":
    main()
