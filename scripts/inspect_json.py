import sqlite3

conn = sqlite3.connect('backend/data/global.db')
c = conn.cursor()
c.execute("SELECT vlm_result_json, manual_json_text FROM jobs WHERE project_id='T0' LIMIT 2")
rows = c.fetchall()

for i, row in enumerate(rows):
    print(f"\n--- Job {i} ---")
    print("VLM_JSON:", row[0])
    print("MANUAL_JSON:", row[1])
