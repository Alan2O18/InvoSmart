import re

with open('tests/test_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add pytest.mark.asyncio to classes
text = text.replace('@pytest.mark.engine\nclass', '@pytest.mark.engine\n@pytest.mark.asyncio\nclass')

# Convert def test_ to async def test_
text = re.sub(r'    def test_', r'    async def test_', text)

# Add await to async methods
async_methods = [
    'engine.create_project',
    'engine.run_splitting',
    'engine.run_split_single',
    'engine.run_processing',
    'engine.run_single_processing',
    'engine.get_raw_files',
    'engine.add_project_files',
    'engine.delete_job',
    'engine.run_excel',
    'engine.archive_project',
    'engine.regenerate_project',

    'engine.project_repo.register_project',
    'engine.project_repo.get_project',
    'engine.project_repo.update_project_status',
    'engine.project_repo.upsert_group',
    'engine.project_repo.list_groups',
    'engine.project_repo.delete_group',
    'engine.project_repo.update_activity_info',

    'tm.insert_job',
    'tm.update_job',
    'tm.list_jobs',
    'tm.get_job',

    'job_repo.list_jobs'
]

for m in async_methods:
    text = text.replace(m + '(', 'await ' + m + '(')

with open('tests/test_engine.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("test_engine.py rewritten successfully!")
