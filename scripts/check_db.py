import sqlite3
conn = sqlite3.connect("global.db")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("TABLES:", tables)
projs = conn.execute("SELECT project_id, name FROM projects").fetchall()
print("PROJECTS:", projs)
jobs = conn.execute("SELECT project_id, COUNT(*) as cnt FROM jobs GROUP BY project_id").fetchall()
print("JOBS BY PROJECT:", jobs)
conn.close()
