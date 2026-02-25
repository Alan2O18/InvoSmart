import sqlite3
import json

conn = sqlite3.connect('backend/data/global.db')
c = conn.cursor()
c.execute("SELECT vlm_result_json, manual_json_text FROM jobs WHERE project_id='T0' LIMIT 2")
rows = c.fetchall()

with open('json_utf8.txt', 'w', encoding='utf-8') as f:
    for i, row in enumerate(rows):
        f.write(f"\n--- Job {i} ---\n")
        f.write(f"VLM_JSON: {row[0]}\n")
        f.write(f"MANUAL_JSON: {row[1]}\n")
