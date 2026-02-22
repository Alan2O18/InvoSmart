from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys
import os

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Initialize logging BEFORE other imports
from backend.utils.logger import setup_logging
setup_logging()

from backend.routers import router as projects_router, websocket
from backend.routers.suggestions import router as suggestions_router
from backend.routers.config import router as config_router

from fastapi.staticfiles import StaticFiles
import json

# Load config to get workspace root
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)
workspace_root = config["project_manager_settings"]["workspace_root"]
global_db_path = config["project_manager_settings"]["global_db_path"]

# Ensure workspace root exists to prevent StaticFiles mount crash
os.makedirs(workspace_root, exist_ok=True)

print("="*60)
print(f"🚀 AI Agent Lab Server Starting...")
print(f"📂 Workspace Root: {os.path.abspath(workspace_root)}")
print(f"🛢️  Global DB Path:  {os.path.abspath(global_db_path)}")
print("="*60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Engine before accepting requests
    from backend.dependencies import get_engine, reset_engine
    get_engine()
    yield
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

# Include Routers
app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(suggestions_router, prefix="/api", tags=["suggestions"])
app.include_router(config_router, prefix="/api/config", tags=["config"])
app.include_router(websocket.router, tags=["websocket"])

@app.get("/")
def read_root():
    return {"message": "AI Agent Lab Backend is running"}
