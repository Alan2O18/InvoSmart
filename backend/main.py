from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from contextlib import suppress
import asyncio
import logging
import sys
import os

# Calculate absolute project root once
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(PROJECT_ROOT)

# Initialize logging BEFORE other imports
from backend.utils.logger import setup_logging
setup_logging()

logger = logging.getLogger(__name__)

from backend.routers import router as projects_router, websocket
from backend.routers.suggestions import router as suggestions_router
from backend.routers.config import router as config_router
from backend.routers.pdf import router as pdf_router
from backend.routers.voucher import router as voucher_router
from backend.routers.stamps import router as stamps_router

from fastapi.staticfiles import StaticFiles
import json

# Load config to get workspace root
from backend.utils.config import load_config
config = load_config()

# Set defaults if keys are missing in config
pm_settings = config.get("project_manager_settings", {})
workspace_root = pm_settings.get("workspace_root", "workspace")
global_db_path = pm_settings.get("global_db_path", "backend/data/global.db")


# Ensure workspace root exists to prevent StaticFiles mount crash
os.makedirs(workspace_root, exist_ok=True)
stamps_static_root = os.path.join(PROJECT_ROOT, "backend", "data", "stamps")
os.makedirs(stamps_static_root, exist_ok=True)

print("="*60)
print(f"🚀 AI Agent Lab Server Starting...")
print(f"📂 Workspace Root: {os.path.abspath(workspace_root)}")
print(f"🛢️  Global DB Path:  {os.path.abspath(global_db_path)}")
print("="*60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and Engine before accepting requests
    from backend.dependencies import get_engine, reset_engine
    from backend.database.core import init_db
    
    # 1. Initialize global database tables asynchronously
    await init_db()
    
    # 2. Setup Engine (workers start conditionally if start_workers=True)
    engine = get_engine()
    
    # 3. Recover pending tasks that might have crashed previously
    await engine.recover_pending_tasks()

    startup_tasks: list[asyncio.Task] = []

    async def _startup_housekeeping():
        processing_settings = config.get("processing_settings", {})
        cleanup_max_age = int(processing_settings.get("preview_cache_cleanup_max_age_hours", 24))
        optimize_on_startup = bool(processing_settings.get("optimize_jxl_on_startup", True))

        try:
            cache_summary = await engine.cleanup_preview_cache(max_age_hours=cleanup_max_age)
            cache_projects = cache_summary.get("projects") if isinstance(cache_summary, dict) else None
            cache_deleted = cache_summary.get("deleted_files") if isinstance(cache_summary, dict) else None
            logger.info(
                "[Startup] Preview cache cleanup done: projects=%s deleted_files=%s",
                cache_projects,
                cache_deleted,
            )
        except Exception as cache_err:  # noqa: BLE001
            logger.warning(f"[Startup] Preview cache cleanup failed: {cache_err}")

        if optimize_on_startup:
            try:
                optimize_summary = await engine.optimize_jxl_storage_all_projects(force=False)
                optimize_count = optimize_summary.get("optimized_jobs") if isinstance(optimize_summary, dict) else None
                optimize_failed = optimize_summary.get("failed_jobs") if isinstance(optimize_summary, dict) else None
                logger.info(
                    "[Startup] JXL optimization done: optimized_jobs=%s failed_jobs=%s",
                    optimize_count,
                    optimize_failed,
                )
            except Exception as optimize_err:  # noqa: BLE001
                logger.warning(f"[Startup] JXL optimization failed: {optimize_err}")

    startup_tasks.append(asyncio.create_task(_startup_housekeeping()))
    
    yield

    for task in startup_tasks:
        if task.done():
            with suppress(Exception):
                task.result()
            continue
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    # Shutdown: Stop worker threads gracefully
    reset_engine()


app = FastAPI(title="AI Agent Lab API", lifespan=lifespan)

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development, allow all. In production, specify the frontend URL.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=workspace_root), name="static")
app.mount("/stamps-static", StaticFiles(directory=stamps_static_root), name="stamps-static")

# Include Routers
app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(suggestions_router, prefix="/api", tags=["suggestions"])
app.include_router(config_router, prefix="/api/config", tags=["config"])
app.include_router(pdf_router, prefix="/api/pdf", tags=["pdf"])
app.include_router(voucher_router, prefix="/api/voucher", tags=["voucher"])
app.include_router(stamps_router, prefix="/api", tags=["stamps"])
app.include_router(websocket.router, tags=["websocket"])

@app.get("/")
def read_root():
    return {"message": "AI Agent Lab Backend is running"}
