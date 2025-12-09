from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add the parent directory to sys.path to allow imports from the root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.routers import router as projects_router, websocket

from fastapi.staticfiles import StaticFiles
import json

# Load config to get workspace root
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)
workspace_root = config["project_manager_settings"]["workspace_root"]

app = FastAPI(title="AI Agent Lab API")

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
app.include_router(websocket.router, tags=["websocket"])

@app.get("/")
def read_root():
    return {"message": "AI Agent Lab Backend is running"}
