"""Migrate projects, groups, vocabulary from global_projects.db.bak into global.db"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
OLD_DB = ROOT / "global_projects.db"  # not yet renamed, still has the data
NEW_DB = ROOT / "global.db"

if not OLD_DB.exists():
    print(f"ERROR: {OLD_DB} not found")
    exit(1)

src = sqlite3.connect(str(OLD_DB)); src.row_factory = sqlite3.Row
dst = sqlite3.connect(str(NEW_DB)); dst.row_factory = sqlite3.Row

# Ensure projects table in global.db
dst.executescript("""
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,
  name TEXT, root_path TEXT, status TEXT,
  created_at REAL, updated_at REAL, notes TEXT, metadata TEXT
);
CREATE TABLE IF NOT EXISTS groups (
  group_name TEXT PRIMARY KEY, leader_name TEXT
);
CREATE TABLE IF NOT EXISTS vocabulary (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category TEXT, term TEXT, frequency INTEGER DEFAULT 1,
  last_used_at REAL, UNIQUE(category, term)
);
""")
dst.commit()

stats = {"projects": 0, "groups": 0, "vocabulary": 0}
for row in src.execute("SELECT * FROM projects"):
    d = dict(row)
    dst.execute("INSERT OR REPLACE INTO projects (project_id,name,root_path,status,created_at,updated_at,notes,metadata) VALUES (?,?,?,?,?,?,?,?)",
                (d["project_id"], d.get("name"), d.get("root_path"), d.get("status"),
                 d.get("created_at"), d.get("updated_at"), d.get("notes"), d.get("metadata")))
    stats["projects"] += 1

try:
    for row in src.execute("SELECT * FROM groups"):
        d = dict(row)
        dst.execute("INSERT OR REPLACE INTO groups VALUES (?,?)", (d["group_name"], d.get("leader_name")))
        stats["groups"] += 1
except Exception: pass

try:
    for row in src.execute("SELECT * FROM vocabulary"):
        d = dict(row)
        dst.execute("INSERT OR IGNORE INTO vocabulary (category,term,frequency,last_used_at) VALUES (?,?,?,?)",
                    (d.get("category"), d.get("term"), d.get("frequency",1), d.get("last_used_at")))
        stats["vocabulary"] += 1
except Exception: pass

dst.commit()
src.close(); dst.close()
print(f"Migrated: {stats}")
print("Done! global.db now has projects + jobs.")
