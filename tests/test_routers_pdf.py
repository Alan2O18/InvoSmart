import os
import pytest
from httpx import AsyncClient, ASGITransport
import fitz
import json

from backend.main import app
from backend.dependencies import get_engine

@pytest.fixture
def mock_engine(tmp_path):
    # Setup a mock engine with a real enough environment to test routing and file saving
    from backend.engine.core import Engine
    
    config = {
        "project_manager_settings": {
            "workspace_root": str(tmp_path / "workspace"),
            "global_db_path": str(tmp_path / "global.db")
        }
    }
    
    # Init DB tables
    from backend.database.core import Base
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    
    test_db_url = f"sqlite+aiosqlite:///{config['project_manager_settings']['global_db_path']}"
    db_engine = create_async_engine(test_db_url)
    
    async def init_tables():
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    session_factory = sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    
    engine = Engine(config=config, start_workers=False, session_factory=session_factory)
            
    async def setup_proj():
        await engine.project_repo.setup_project("proj1", name="Test Project")
        
    async def do_async_setup():
        await init_tables()
        await setup_proj()

    import anyio
    anyio.run(do_async_setup)
    
    # override get_engine dependency
    app.dependency_overrides[get_engine] = lambda: engine
    
    yield engine
    
    app.dependency_overrides.pop(get_engine, None)

def create_test_pdf(path: str):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test PDF")
    doc.save(path)
    doc.close()

@pytest.mark.asyncio
async def test_upload_pdf(mock_engine, tmp_path):
    pdf_path = tmp_path / "test_upload.pdf"
    create_test_pdf(str(pdf_path))
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with open(pdf_path, "rb") as f:
            response = await client.post(
                "/api/pdf/proj1/pdf",
                files={"files": ("test_upload.pdf", f, "application/pdf")}
            )
        
    assert response.status_code == 200
    assert response.json()["status"] == "added"
    
    # Verify file was placed in 原始輸入
    root = mock_engine.project_repo._project_root("proj1")
    assert (root / "原始輸入" / "test_upload.pdf").exists()
    
    # Verify first page was converted to jpg in 分割發票
    split_dir = root / "分割發票"
    jpgs = list(split_dir.glob("test_upload_page0_*.jpg"))
    assert len(jpgs) == 1
    
    # Verify job was created
    job_repo = mock_engine.get_job_repo("proj1")
    jobs = await job_repo.list_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    
    job_details = await job_repo.get_job(job["job_id"])
    assert "test_upload_page0_" in job_details["image_path"]
    assert "test_upload.pdf" in job_details["source_pdf_path"]
    assert job_details["status"] == "ready"
    assert job_details["pdf_status"] == "uploaded"

@pytest.mark.asyncio
async def test_execute_pdf_commands(mock_engine):
    # 1. Manually add a job to db
    job_repo = mock_engine.get_job_repo("proj1")
    job_id = "job-12345"
    await job_repo.insert_job(job_id, "dummy.jpg", "done")
    await job_repo.update_job(job_id, source_pdf_path="dummy.pdf", pdf_status="uploaded")
    
    commands = {
        "page_order": [0],
        "stamps": []
    }
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            f"/api/pdf/proj1/{job_id}/commands",
            json=commands
        )
    
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    
    # Verify it went into the pdf task queue
    assert mock_engine.pdf_task_queue.qsize() == 1
    task = mock_engine.pdf_task_queue.get()
    assert task[0] == "proj1"
    assert task[1] == "job-12345"
    assert task[2] == commands
    
    # verify status updated to pending_compression
    job = await job_repo.get_job(job_id)
    assert job["pdf_status"] == "pending_compression"
