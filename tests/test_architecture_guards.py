import importlib.util
from pathlib import Path


def _load_guard_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_architecture_guards.py"
    spec = importlib.util.spec_from_file_location("check_architecture_guards", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_architecture_guard_reports_violations(tmp_path, monkeypatch, capsys):
    guard = _load_guard_module()

    backend = tmp_path / "backend"
    routers = backend / "routers"
    routers.mkdir(parents=True, exist_ok=True)

    violating_router = routers / "violating.py"
    violating_router.write_text("import cv2\n\n\ndef route(db):\n    db.execute('select 1')\n", encoding="utf-8")

    long_file = backend / "too_long.py"
    long_file.write_text("\n".join(["x = 1"] * 801), encoding="utf-8")

    monkeypatch.setattr(guard, "ROOT", tmp_path)
    monkeypatch.setattr(guard, "BACKEND", backend)
    monkeypatch.setattr(guard, "ROUTERS", routers)

    result = guard.main()
    out = capsys.readouterr().out

    assert result == 1
    assert "[MAX_LINES]" in out
    assert "[ROUTER_IMPORT]" in out
    assert "[ROUTER_DB]" in out


def test_architecture_guard_passes_clean_tree(tmp_path, monkeypatch, capsys):
    guard = _load_guard_module()

    backend = tmp_path / "backend"
    routers = backend / "routers"
    routers.mkdir(parents=True, exist_ok=True)

    clean_router = routers / "clean.py"
    clean_router.write_text(
        "from fastapi import APIRouter\n\nrouter = APIRouter()\n\n@router.get('/')\ndef ok():\n    return {'status': 'ok'}\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(guard, "ROOT", tmp_path)
    monkeypatch.setattr(guard, "BACKEND", backend)
    monkeypatch.setattr(guard, "ROUTERS", routers)

    result = guard.main()
    out = capsys.readouterr().out

    assert result == 0
    assert "Architecture guard checks passed." in out
