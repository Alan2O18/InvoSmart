"""查詢人工修正的收據資料"""
import sqlite3
import json

conn = sqlite3.connect('jobs.db')
cursor = conn.cursor()

# 查看表結構
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', [t[0] for t in tables])

# 查看 jobs 表結構
cursor.execute("PRAGMA table_info(jobs)")
columns = cursor.fetchall()
print('\nColumns:', [c[1] for c in columns])

# 查找有資料的記錄
cursor.execute('''
    SELECT * FROM jobs LIMIT 1
''')
results = cursor.fetchall()
print(f'\nSample row:')
for i, col in enumerate(columns):
    if results:
        print(f'  {col[1]}: {str(results[0][i])[:100]}')
results = cursor.fetchall()
print(f'\nFound {len(results)} records with llm_result_json')

for row in results:
    print(f'\n=== ID: {row[0]} ===')
    print(f'Path: {row[1]}')
    try:
        data = json.loads(row[2])
        header = data.get('header', {})
        print(f'  Buyer: {header.get("buyer")}')
        print(f'  Date: {header.get("date")}')
        items = data.get('items', [])
        print(f'  Items: {len(items)}')
        for item in items[:3]:
            print(f'    - {item.get("name")}: {item.get("total")}')
        audit = data.get('audit', {})
        corrections = audit.get('corrections', [])
        if corrections:
            print(f'  Corrections: {len(corrections)}')
            for c in corrections:
                print(f'    - {c.get("source")}: {c.get("description", "")[:50]}')
    except Exception as e:
        print(f'  Parse error: {e}')

conn.close()
