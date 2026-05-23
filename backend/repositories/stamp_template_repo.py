import json
import shutil
from pathlib import Path
from typing import List, Optional

class StampTemplateRepository:
    def __init__(self, root_dir: Optional[Path] = None):
        if root_dir is None:
            self.root_dir = Path(__file__).resolve().parents[2] / "backend" / "data" / "stamp_templates"
        else:
            self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _template_dir(self, template_id: str) -> Path:
        return self.root_dir / template_id

    def _template_meta_path(self, template_id: str) -> Path:
        return self._template_dir(template_id) / "template.json"

    def read_meta(self, template_id: str) -> Optional[dict]:
        path = self._template_meta_path(template_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def write_meta(self, template_id: str, meta: dict) -> None:
        path = self._template_meta_path(template_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_template_ids(self) -> List[str]:
        if not self.root_dir.exists():
            return []
        ids = [child.name for child in self.root_dir.iterdir() if child.is_dir()]
        def get_update_time(template_id: str) -> float:
            meta = self.read_meta(template_id)
            return meta.get("updated_at", 0) if meta else 0
        return sorted(ids, key=get_update_time, reverse=True)

    def delete_template(self, template_id: str) -> bool:
        template_dir = self._template_dir(template_id)
        if not template_dir.exists():
            return False
        shutil.rmtree(template_dir, ignore_errors=True)
        return True
