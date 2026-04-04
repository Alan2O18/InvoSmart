import json
import os
from backend.repositories.project_repository import ProjectRepository
from backend.repositories.job_repository import JobRepository
from backend.engine.word_exporter import WordExporter

config = {
    "global_db_path": "backend/data/global.db",
    "workspace_root": "backend/data/workspace"
}
repo = ProjectRepository(config)
project = repo.get_project("T0")

# Inject fake test data into metadata
if "metadata" not in project:
    project["metadata"] = {}

meta = project["metadata"]
meta["budgetDate"] = "2026-02-01"
meta["finalAccountDate"] = "2026-03-01"
meta["subsidyReason"] = "Research Grant"
meta["subsidyMethod"] = "Direct Transfer"
meta["balanceHandling"] = "Return to school"
meta["overdraftHandling"] = "Self-funded"

meta["budgetIncome"] = [
    {"name": "School Funding", "amount": 5000, "note": "Approved"},
    {"name": "Department Fund", "amount": 1000, "note": ""}
]

meta["budgetExpense"] = [
    {"name": "Lunch Box", "qty": 10, "price": 100, "total": 1000, "purpose": "Meeting"},
    {"name": "Train Tickets", "qty": 2, "price": 500, "total": 1000, "purpose": "Transportation"}
]

repo.update_project_metadata("T0", meta)

# Run export
job_repo = JobRepository("T0", "backend/data/global.db")
exporter = WordExporter(repo)
template_path = "dev_data/空白 模板 (1).docx"

print("Starting export...")
try:
    path = exporter.process_export("T0", template_path, job_repo)
    print(f"Success! Output to {path}")
except Exception as e:
    import traceback
    traceback.print_exc()
