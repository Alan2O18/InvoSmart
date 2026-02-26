import re
import sys

files = sys.argv[1:]

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
    'engine.project_repo.list_projects',
    'engine.project_repo.update_project_status',
    'engine.project_repo.upsert_group',
    'engine.project_repo.list_groups',
    'engine.project_repo.delete_group',
    'engine.project_repo.update_activity_info',

    'tm.insert_job',
    'tm.update_job',
    'tm.list_jobs',
    'tm.get_job',
    'tm.save_manual_json',
    'tm.complete_vlm',
    'tm.get_job_details',
    'tm.get_display_result',
    'tm.fail_job',

    'job_repo.list_jobs',
    'job_repo.insert_job',
    'job_repo.update_job',
    'job_repo.get_job',
    'job_repo.fail_job'
]

for file_path in files:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            
        # Add pytest.mark.asyncio to classes
        text = text.replace('class Test', '@pytest.mark.asyncio\nclass Test')
        
        # Convert def test_ to async def test_
        text = re.sub(r'    def test_', r'    async def test_', text)
        
        # Convert def setup_ to async def setup_ (like async setups) if they call awaits
        # Actually pytest fixtures need @pytest_asyncio.fixture if they are async.
        # So we'll leave fixtures alone mostly, or we manually patch them.
        
        # Add await to async methods
        for m in async_methods:
            text = text.replace(m + '(', 'await ' + m + '(')
            
        # Remove double awaits if any
        text = text.replace('await await ', 'await ')
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
            
        print(f"{file_path} rewritten successfully!")
    except FileNotFoundError:
        print(f"{file_path} not found.")
