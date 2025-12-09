# Archive Handler - 專案封存功能
import logging
import os
import shutil
import tempfile
import zipfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ArchiveHandler:
    """Handles project archiving (7z/zip compression)."""
    
    def __init__(self, project_manager):
        self.project_manager = project_manager
    
    def seal_project(
        self,
        project_id: str,
        dest_folder: Optional[str] = None,
        include_raw: bool = True,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """
        Seal (archive) a project to 7z or zip format.
        
        Args:
            project_id: Project identifier
            dest_folder: Optional destination folder for archive
            include_raw: Whether to include raw input files
            debug: Whether to include debug information
            
        Returns:
            Dictionary with success status, method, archive path, and debug info
        """
        root = self.project_manager._project_root(project_id)
        if not root.exists():
            raise FileNotFoundError("project root not found")
        
        # Use workspace root from project manager to determine default archives location
        workspace_root = self.project_manager.project_setup.workspace_root
        dest_root = (
            Path(dest_folder) if dest_folder else workspace_root / "archives"
        )
        dest_root.mkdir(parents=True, exist_ok=True)

        sevenz = shutil.which("7z") or shutil.which("7za") or shutil.which("7zr")
        archive_name = f"{project_id}.7z" if sevenz else f"{project_id}.zip"
        dest = dest_root / archive_name

        if sevenz:
            # 建 command
            cmd = [sevenz, "a", "-t7z", "-mx=9", str(dest), str(root)]
            # 若不 include_raw，先建立暫時資料夾複製要壓縮的內容（排除 原始輸入）
            temp_target = None
            if not include_raw:
                temp_target = Path(tempfile.mkdtemp(prefix="pm_seal_"))
                # 複製 root 的內容到 temp_target，排除 原始輸入
                for p in root.iterdir():
                    if p.name == "原始輸入":
                        continue
                    destp = temp_target / p.name
                    if p.is_dir():
                        shutil.copytree(p, destp)
                    else:
                        shutil.copy2(p, destp)
                cmd = [sevenz, "a", "-t7z", "-mx=9", str(dest), str(temp_target)]
            # run with capture
            proc = subprocess.run(cmd, capture_output=True, text=True)
            debug_info = {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
            if temp_target:
                shutil.rmtree(temp_target, ignore_errors=True)
            if proc.returncode == 0:
                self.project_manager.update_project_status(project_id, "SEALED")
                return {
                    "success": True,
                    "method": "7z",
                    "archive_path": str(dest),
                    "debug": debug_info if debug else None,
                }
            else:
                logger.error(
                    "7z failed: returncode=%s stderr=%s", proc.returncode, proc.stderr
                )
                # fallback to zip below, but include debug info
                zip_debug = debug_info
        else:
            zip_debug = {"note": "7z not found, fallback to zip"}

        # fallback to zip
        archive_name_zip = f"{project_id}.zip"
        dest_zip = dest_root / archive_name_zip
        fd, tmpzip = tempfile.mkstemp(dir=str(dest_root), suffix=".tmp")
        os.close(fd)
        try:
            with zipfile.ZipFile(tmpzip, "w", zipfile.ZIP_DEFLATED) as z:
                for r, dirs, files in os.walk(root):
                    if (
                        not include_raw
                        and Path(r).relative_to(root).parts
                        and Path(r).relative_to(root).parts[0] == "原始輸入"
                    ):
                        continue
                    for f in files:
                        full = Path(r) / f
                        arc = str(Path(project_id) / Path(r).relative_to(root) / f)
                        z.write(str(full), arc)
            os.replace(tmpzip, str(dest_zip))
            self.project_manager.update_project_status(project_id, "SEALED")
            return {
                "success": True,
                "method": "zip",
                "archive_path": str(dest_zip),
                "debug": zip_debug if debug else None,
            }
        except Exception as e:
            try:
                os.unlink(tmpzip)
            except Exception:
                pass
            logger.exception("zip fallback failed")
            return {
                "success": False,
                "method": "zip",
                "archive_path": None,
                "debug": str(e),
            }
