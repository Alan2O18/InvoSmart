# Projects Router - 專案 CRUD 端點
import os
import logging
import json
from collections import defaultdict
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from backend.database import core as database_core
from backend.dependencies import get_engine
from backend.engine.core import Engine
from backend.repositories.project_repository import ProjectArchivedError
from backend.repositories.suggestion_repository import SuggestionRepository
from backend.utils.utils import handle_upload_files

logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectCreate(BaseModel):
    project_id: str
    metadata: Optional[dict] = None


def _split_people(raw_value) -> list[str]:
    if raw_value is None:
        return []

    if isinstance(raw_value, (list, tuple, set)):
        candidates = [str(v).strip() for v in raw_value]
    else:
        text = str(raw_value).strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    candidates = [str(v).strip() for v in parsed]
                else:
                    candidates = [text]
            except Exception:
                candidates = [text]
        else:
            normalized = (
                text.replace("\n", "、")
                .replace(",", "、")
                .replace("，", "、")
                .replace(";", "、")
                .replace("；", "、")
            )
            candidates = [part.strip() for part in normalized.split("、")]

    unique: list[str] = []
    for name in candidates:
        if name and name not in unique:
            unique.append(name)
    return unique


def _collect_project_option_suggestions(metadata: dict) -> dict[str, list[str]]:
    if not isinstance(metadata, dict):
        return {}

    buckets: dict[str, set[str]] = defaultdict(set)


    location = str(metadata.get("location") or "").strip()
    if location:
        buckets["location"].add(location)

    group_name = str(metadata.get("group") or "").strip()
    if group_name:
        buckets["group_name"].add(group_name)

    for field in ("leader", "coordinator", "generalAffairs", "leader_names"):
        for person in _split_people(metadata.get(field)):
            buckets["person_name"].add(person)

    for item in metadata.get("budgetIncome", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            buckets["budget_income_item"].add(name)

    for item in metadata.get("budgetExpense", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            buckets["expense_category"].add(name)

    return {cat: sorted(values) for cat, values in buckets.items() if values}


async def _persist_project_metadata_suggestions(metadata: dict) -> None:
    if not isinstance(metadata, dict) or database_core.AsyncSessionLocal is None:
        return

    collected = _collect_project_option_suggestions(metadata)
    if not collected:
        return

    repo = SuggestionRepository(session_factory=lambda: database_core.AsyncSessionLocal())
    for category, values in collected.items():
        if values:
            await repo.bulk_add(category, values)


@router.get("/")
async def list_projects(engine: Engine = Depends(get_engine)):
    """List all projects."""
    return await engine.project_repo.list_projects()


@router.post("/")
async def create_project(
    project_id: str = Form(...),
    metadata: str = Form(None),  # JSON string
    files: Optional[List[UploadFile]] = File(None),
    engine: Engine = Depends(get_engine)
):
    """Create a new project, optionally with uploaded files."""
    try:
        meta_dict = {}
        activity_name = None
        if metadata:
            try:
                meta_dict = json.loads(metadata)
                activity_name = meta_dict.get('name') or meta_dict.get('projectName')
            except Exception:
                pass

        if files:
            async with handle_upload_files(files) as saved_file_paths:
                result = await engine.create_project(project_id, saved_file_paths, name=activity_name, metadata=meta_dict)
                try:
                    await _persist_project_metadata_suggestions(meta_dict)
                except Exception as suggest_err:
                    logger.warning(f"Failed to persist project suggestions for {project_id}: {suggest_err}")
                return result
        else:
            result = await engine.create_project(project_id, [], name=activity_name, metadata=meta_dict)
            try:
                await _persist_project_metadata_suggestions(meta_dict)
            except Exception as suggest_err:
                logger.warning(f"Failed to persist project suggestions for {project_id}: {suggest_err}")
            return result
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{project_id}")
async def update_project(project_id: str, metadata: dict, engine: Engine = Depends(get_engine)):
    """Update project metadata."""
    try:
        await engine.project_repo.update_project_metadata(project_id, metadata)
        try:
            await _persist_project_metadata_suggestions(metadata)
        except Exception as suggest_err:
            logger.warning(f"Failed to persist project suggestions for {project_id}: {suggest_err}")
        return await engine.project_repo.get_project(project_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{project_id}")
async def delete_project(project_id: str, engine: Engine = Depends(get_engine)):
    """Delete a project."""
    try:
        return await engine.project_repo.delete_project(project_id)
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}/detail")
async def get_project_detail(project_id: str, engine: Engine = Depends(get_engine)):
    """Get full project payload (including metadata)."""
    try:
        project = await engine.project_repo.get_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detail for {project_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{project_id}")
async def get_project_status(project_id: str, engine: Engine = Depends(get_engine)):
    """Get project status and details."""
    try:
        await engine.project_repo.sync_status_to_db(project_id)
        return await engine.project_repo.get_project_status(project_id)
    except Exception as e:
        logger.error(f"Error getting status for {project_id}: {e}")
        raise HTTPException(status_code=404, detail="Project not found")


@router.post("/{project_id}/activity_info")
async def update_activity_info(project_id: str, info: dict, engine: Engine = Depends(get_engine)):
    """Update project activity info."""
    try:
        await engine.project_repo.update_activity_info(project_id, info)
        try:
            await _persist_project_metadata_suggestions(info)
        except Exception as suggest_err:
            logger.warning(f"Failed to persist project suggestions for {project_id}: {suggest_err}")
        return await engine.project_repo.get_project(project_id)
    except ProjectArchivedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating activity info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{project_id}/generate-voucher-pdf")
async def generate_voucher_pdf(project_id: str, engine: Engine = Depends(get_engine)):
    """產生並下載憑證黏貼 PDF"""
    try:
        pdf_path = await engine.generate_voucher_pdf(project_id)
        if not os.path.exists(pdf_path):
            raise HTTPException(status_code=404, detail="PDF generation failed")
            
        return FileResponse(
            path=pdf_path,
            filename=f"憑證黏貼_{project_id}.pdf",
            media_type="application/pdf"
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except Exception as e:
        logger.error(f"Error generating voucher PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
