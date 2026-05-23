import json
import shutil
from pathlib import Path
from typing import List, Optional

class PdfTaskRepository:
    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            self.root_dir = Path(__file__).resolve().parents[2] / "backend" / "data" / "pdf_tasks"
        else:
            self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _task_dir(self, task_id: str) -> Path:
        return self.root_dir / task_id

    def _task_meta_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "task.json"

    def _task_pdf_path(self, task_id: str) -> Path:
        return self._task_dir(task_id) / "working.pdf"

    def read_meta(self, task_id: str) -> Optional[dict]:
        path = self._task_meta_path(task_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def write_meta(self, task_id: str, meta: dict) -> None:
        path = self._task_meta_path(task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_task_ids(self) -> List[str]:
        if not self.root_dir.exists():
            return []
        ids = [child.name for child in self.root_dir.iterdir() if child.is_dir()]
        def get_update_time(task_id: str) -> float:
            meta = self.read_meta(task_id)
            return meta.get("updated_at", 0) if meta else 0
        return sorted(ids, key=get_update_time, reverse=True)

    def delete_task(self, task_id: str) -> bool:
        task_dir = self._task_dir(task_id)
        if not task_dir.exists():
            return False
        shutil.rmtree(task_dir, ignore_errors=True)
        return True

    def write_pdf_content(self, task_id: str, content: bytes) -> Path:
        pdf_path = self._task_pdf_path(task_id)
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(content)
        return pdf_path
