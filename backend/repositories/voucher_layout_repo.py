from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict


def sanitize_project_id(project_id: str) -> str:
    sanitized = re.sub(r"[\\/]+", "_", project_id)
    sanitized = sanitized.replace("..", "_")
    sanitized = re.sub(r"[^A-Za-z0-9_.-]", "_", sanitized)
    return sanitized or "unknown"


class VoucherLayoutRepository:
    def __init__(self, layout_root: str):
        self.layout_root = Path(layout_root)

    def _layout_path(self, project_id: str) -> Path:
        safe_project_id = sanitize_project_id(project_id)
        return self.layout_root / safe_project_id / "voucher_layout.json"

    def load_layout(self, project_id: str) -> Dict[str, Any]:
        path = self._layout_path(project_id)
        if not path.exists():
            return {"globalPrefix": "", "startIndex": 1, "pages": []}
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if isinstance(data, dict):
            return data
        return {"globalPrefix": "", "startIndex": 1, "pages": []}

    def save_layout(self, project_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        path = self._layout_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)

        with tmp_path.open("r", encoding="utf-8") as file:
            json.load(file)

        os.replace(tmp_path, path)
        return {"status": "success"}
