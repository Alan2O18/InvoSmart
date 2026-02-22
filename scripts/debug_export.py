import traceback
from backend.engine.excel_exporter import ExcelExporter
from backend.repositories.project_repository import ProjectRepository
from backend.repositories.job_repository import JobRepository
from pathlib import Path

def test_export():
    try:
        class MockEngine:
            global_db_path = "global.db"
        
        # Instantiate a real Project repo.
        project_repo = ProjectRepository(db_path="global.db")
        
        # Grab the first active project or create a mock.
        projects = project_repo.list_projects()
        if not projects:
            print("No projects to export.")
            return

        project_id = projects[0]["project_id"]
        print(f"Testing export for {project_id}")
        
        exporter = ExcelExporter(project_repo)
        
        out_path = exporter.archive_to_excel(project_id, Path("."))
        print(f"SUCCESS: Exported to {out_path}")
    except Exception as e:
        print("FAILED WITH EXCEPTION:")
        traceback.print_exc()

if __name__ == "__main__":
    test_export()
