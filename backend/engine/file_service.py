import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class FileService:
    """Service for lightweight raw file listing and deletion operations."""

    SUPPORTED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".jxl"}

    def __init__(self, project_repo):
        self.project_repo = project_repo

    def _resolve_project_path(self, root: Path, raw_path: Optional[str], preferred_dir: Optional[str] = None) -> Optional[Path]:
        if not raw_path:
            return None

        path = Path(str(raw_path))
        candidates: list[Path] = []
        if path.is_absolute():
            candidates.append(path)
        else:
            candidates.append(root / path)
            if preferred_dir:
                candidates.append(root / preferred_dir / path.name)

        for candidate in candidates:
            resolved = candidate.resolve(strict=False)
            if resolved.exists():
                return resolved

        if candidates:
            return candidates[0].resolve(strict=False)
        return None

    @staticmethod
    def _is_within_root(root: Path, target: Path) -> bool:
        try:
            target.resolve(strict=False).relative_to(root.resolve(strict=False))
            return True
        except Exception:
            return False

    def get_raw_files(self, project_id: str) -> list[dict]:
        try:
            root = self.project_repo._project_root(project_id)
            raw_dir = root / "原始輸入"
            split_dir = root / "分割發票"

            if not raw_dir.exists():
                return []

            split_names = []
            if split_dir.exists():
                split_names = [
                    p.name
                    for p in split_dir.iterdir()
                    if p.is_file() and p.suffix.lower() in self.SUPPORTED_IMAGE_SUFFIXES
                ]

            raw_files: list[dict] = []
            for raw_path in raw_dir.iterdir():
                if not raw_path.is_file() or raw_path.suffix.lower() not in self.SUPPORTED_IMAGE_SUFFIXES:
                    continue

                base_name = raw_path.stem
                split_count = 0
                for split_name in split_names:
                    if split_name.startswith(base_name + "_split_"):
                        split_count += 1

                raw_files.append(
                    {
                        "filename": raw_path.name,
                        "path": str(raw_path),
                        "split_count": split_count,
                    }
                )

            raw_files.sort(key=lambda item: item["filename"])
            return raw_files
        except Exception as e:
            logger.error(f"Error getting raw files for {project_id}: {e}")
            return []

    def delete_raw_file(self, project_id: str, filename: str) -> dict:
        root = self.project_repo._project_root(project_id)
        safe_name = Path(filename).name
        path = root / "原始輸入" / safe_name
        if path.exists():
            os.remove(path)
            return {"status": "deleted"}
        return {"status": "not_found"}
