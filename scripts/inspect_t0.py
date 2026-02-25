import sqlite3
import json

conn = sqlite3.connect('backend/data/global.db')
c = conn.cursor()
c.execute("SELECT vlm_result_json FROM jobs WHERE project_id='T0'")
rows = c.fetchall()

print("Jobs found:", len(rows))
for i, row in enumerate(rows):
    if row[0]:
        try:
            data = json.loads(row[0])
            items = data.get("items", [])
            print(f"Job {i} items:")
            for item in items:
                print(f" - {item.get('name') or item.get('description', '')}: {item.get('total')}")
        except Exception as e:
            print("Error parsing job", i, e)
    else:
        print(f"Job {i} has no vlm_result_json")
