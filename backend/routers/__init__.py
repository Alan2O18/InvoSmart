# Backend Routers Package
# 匯總所有路由器供 main.py 使用

from fastapi import APIRouter
from . import projects, files, processing, jobs, groups, correction

# 主路由器 - 合併所有子路由
router = APIRouter()
router.include_router(projects.router)
router.include_router(files.router)
router.include_router(processing.router)
router.include_router(jobs.router)
router.include_router(groups.router)
router.include_router(correction.router)

__all__ = ["router", "projects", "files", "processing", "jobs", "groups", "correction"]
