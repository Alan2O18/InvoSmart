import pytest
import os
import json
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

from backend.database.models import Base, Project, Group, Job
from backend.repositories.project_repository import ProjectRepository

@pytest.fixture
def repo(async_session_factory, tmp_path):
    config = {"workspace_root": str(tmp_path)}
    return ProjectRepository(config=config, session_factory=async_session_factory)

@pytest.mark.asyncio
async def test_project_crud(repo, async_session_factory):
    # Register Project
    proj_id = "test_1"
    res = await repo.register_project(
        project_id=proj_id, 
        name="Test Proj", 
        root_path="/fake/path", 
        notes="A note", 
        metadata={"key": "val"}
    )
    assert res is None
    
    # Get Project
    p = await repo.get_project(proj_id)
    assert p["project_id"] == proj_id
    assert p["project_name" if "project_name" in p else "name"] == "Test Proj"
    assert p["notes"] == "A note"
    assert p["metadata"] == {"key": "val"}
    
    # List Projects
    projects = await repo.list_projects()
    assert len(projects) == 1
    assert projects[0]["project_id"] == proj_id
    
    # Update Status
    await repo.update_project_status(proj_id, "PROCESSING")
    p = await repo.get_project(proj_id)
    assert p["status"] == "PROCESSING"
    
    # Update Metadata
    await repo.update_project_metadata(proj_id, {"key": "val2", "new_key": 1})
    p = await repo.get_project(proj_id)
    md = p["metadata"]
    assert md["key"] == "val2"
    assert md["new_key"] == 1
    
    # Delete Project
    res = await repo.delete_project(proj_id)
    assert res is None
    assert (await repo.get_project(proj_id)) is None

@pytest.mark.asyncio
async def test_group_crud(repo):
    # Upsert
    res = await repo.upsert_group("Group Alpha", "Leader X")
    assert res is None
    
    # Upsert again (Update)
    await repo.upsert_group("Group Alpha", "Leader Y")
    
    # List
    groups = await repo.list_groups()
    assert len(groups) == 1
    assert groups[0]["group_name"] == "Group Alpha"
    assert groups[0]["leader_name"] == "Leader Y"
    
    # Delete
    del_res = await repo.delete_group("Group Alpha")
    assert del_res is None
    assert len(await repo.list_groups()) == 0

@pytest.mark.asyncio
async def test_update_activity_info(repo):
    proj_id = "activity_proj"
    await repo.register_project(proj_id, "Act", "/pth")
    
    activity = {
        "budgetRange": "1k-5k",
        "members": 5
    }
    await repo.update_activity_info(proj_id, activity)
    
    p = await repo.get_project(proj_id)
    md = p["metadata"]
    assert md["budgetRange"] == "1k-5k"
    assert md["members"] == 5

@pytest.mark.asyncio
async def test_setup_project(repo, tmp_path):
    proj_id = "setup_proj"
    
    # No DB setup yet
    folder = await repo.setup_project(
        project_id=proj_id,
        name="My Proj",
        resume_if_db_exists=True,
        force_setup=False
    )
    
    root_path = folder["project_root"]
    assert os.path.isdir(root_path)
    # Check layout
    assert os.path.exists(os.path.join(root_path, "原始輸入"))
    assert os.path.exists(os.path.join(root_path, "分割發票"))
    
    # Check DB registration
    p = await repo.get_project(proj_id)
    assert p["project_name" if "project_name" in p else "name"] == "My Proj"

@pytest.mark.asyncio
async def test_sync_status_to_db(repo, async_session_factory):
    proj_id = "sync_proj"
    await repo.setup_project(proj_id, name="Sync")
    
    # Inject a done job
    from backend.database.models import Job
    async with async_session_factory() as session:
        session.add(Job(project_id=proj_id, job_id="j1", image_path="f", status="done", vlm_result_json="{}"))
        await session.commit()
        
    await repo.sync_status_to_db(proj_id)
    
    p = await repo.get_project(proj_id)
    assert p["status"] == "PROCESSED"

@pytest.mark.asyncio
async def test_sync_status_to_db_all_done(repo, async_session_factory):
    proj_id = "sync_proj2"
    await repo.setup_project(proj_id, name="Sync2")
    
    # Inject 2 done jobs
    from backend.database.models import Job
    async with async_session_factory() as session:
        session.add(Job(project_id=proj_id, job_id="j1", image_path="f", status="done", vlm_result_json="{}"))
        session.add(Job(project_id=proj_id, job_id="j2", image_path="f", status="done", vlm_result_json="{}"))
        await session.commit()
        
    await repo.sync_status_to_db(proj_id)
    p = await repo.get_project(proj_id)
    assert p["status"] == "PROCESSED"
