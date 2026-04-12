from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
ROUTERS = BACKEND / "routers"

FORBIDDEN_IMPORT_PATTERNS = [
    re.compile(r"^\s*import\s+cv2\b", re.MULTILINE),
    re.compile(r"^\s*from\s+cv2\b", re.MULTILINE),
    re.compile(r"^\s*import\s+numpy\b", re.MULTILINE),
    re.compile(r"^\s*from\s+numpy\b", re.MULTILINE),
]
FORBIDDEN_DB_PATTERNS = [
    re.compile(r"\bdb\.execute\s*\("),
    re.compile(r"\bdb\.add\s*\("),
]


def _iter_python_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def main() -> int:
    violations: list[str] = []

    # Global file-size guard
    for py_file in _iter_python_files(BACKEND):
        line_count = sum(1 for _ in py_file.open("r", encoding="utf-8"))
        if line_count > 800:
            violations.append(f"[MAX_LINES] {py_file.relative_to(ROOT)} has {line_count} lines (>800)")

    # Router-specific guards
    for py_file in _iter_python_files(ROUTERS):
        content = py_file.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_IMPORT_PATTERNS:
            if pattern.search(content):
                violations.append(f"[ROUTER_IMPORT] {py_file.relative_to(ROOT)} contains forbidden import pattern: {pattern.pattern}")
        for pattern in FORBIDDEN_DB_PATTERNS:
            if pattern.search(content):
                violations.append(f"[ROUTER_DB] {py_file.relative_to(ROOT)} contains forbidden DB call pattern: {pattern.pattern}")

    if violations:
        print("Architecture guard violations found:")
        for issue in violations:
            print(f"- {issue}")
        return 1

    print("Architecture guard checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
