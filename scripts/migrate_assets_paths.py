#!/usr/bin/env python3
"""
scripts/migrate_assets_paths.py

一次性資產路徑正規化腳本（P4）

目的：
  將歷史遺留在 dev_data/ 的專案資產遷移到 backend/assets/templates/
  並可選地掃描後端原始碼，確認不再有硬編碼的 dev_data 路徑殘留。

步驟：
  1. 確保 backend/assets/templates/ 目錄存在
  2. 複製（不刪除）dev_data/空白 模板 (1).docx
     → backend/assets/templates/報表範本.docx
  3. 複製（不刪除）dev_data/憑證黏貼用紙.pdf（若存在且 assets/ 版本不存在）
     → backend/assets/templates/憑證黏貼用紙.pdf
  4. 掃描 backend/ 下所有 .py 是否還有殘留的 dev_data/ 硬路徑，並列出警告

使用範例：
  python scripts/migrate_assets_paths.py
  python scripts/migrate_assets_paths.py --dry-run
  python scripts/migrate_assets_paths.py --check-only
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ASSETS_TEMPLATES = PROJECT_ROOT / "backend" / "assets" / "templates"
DEV_DATA = PROJECT_ROOT / "dev_data"

# Mapping: source (in dev_data) → destination (in assets/templates)
COPY_PLAN: list[tuple[Path, Path]] = [
    (DEV_DATA / "空白 模板 (1).docx", ASSETS_TEMPLATES / "報表範本.docx"),
    (DEV_DATA / "憑證黏貼用紙.pdf",  ASSETS_TEMPLATES / "憑證黏貼用紙.pdf"),
]


def _ensure_templates_dir(dry_run: bool) -> None:
    if ASSETS_TEMPLATES.exists():
        return
    print(f"[mkdir] {ASSETS_TEMPLATES}")
    if not dry_run:
        ASSETS_TEMPLATES.mkdir(parents=True, exist_ok=True)


def _copy_assets(dry_run: bool) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {"copied": [], "skipped_src_missing": [], "already_exists": []}
    for src, dst in COPY_PLAN:
        if not src.exists():
            print(f"[skip] Source not found: {src}")
            result["skipped_src_missing"].append(str(src))
            continue
        if dst.exists():
            print(f"[ok]   Destination already exists, no action: {dst.relative_to(PROJECT_ROOT)}")
            result["already_exists"].append(str(dst))
            continue
        rel_src = src.relative_to(PROJECT_ROOT)
        rel_dst = dst.relative_to(PROJECT_ROOT)
        print(f"[copy] {rel_src}  →  {rel_dst}")
        if not dry_run:
            shutil.copy2(src, dst)
        result["copied"].append(str(dst))
    return result


def _scan_hardcoded_devdata(backend_dir: Path) -> list[str]:
    """Return list of '<file>:<lineno>: <line>' where dev_data/ path hard-coding is detected."""
    hits: list[str] = []
    for py_file in sorted(backend_dir.rglob("*.py")):
        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip pure comment lines — only flag executable code with dev_data asset paths
            if stripped.startswith("#"):
                continue
            if "dev_data" in line and (
                "空白" in line or "憑證黏貼" in line or "模板" in line or "template" in line.lower()
            ):
                rel = py_file.relative_to(PROJECT_ROOT)
                hits.append(f"{rel}:{i}: {line.strip()}")
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalise asset paths from dev_data → backend/assets/templates")
    parser.add_argument("--dry-run", action="store_true",
                        help="預覽動作但不實際複製或建立目錄")
    parser.add_argument("--check-only", action="store_true",
                        help="只掃描後端原始碼中的殘留 dev_data 路徑，不執行複製")
    parser.add_argument("--report-path", metavar="FILE",
                        help="完成後寫入 JSON 結果摘要")
    args = parser.parse_args()

    # ── Scan mode ──────────────────────────────────────────────────────────────
    if args.check_only:
        hits = _scan_hardcoded_devdata(PROJECT_ROOT / "backend")
        if hits:
            print(f"\n⚠  殘留硬編碼 dev_data 路徑（{len(hits)} 處）：")
            for h in hits:
                print(f"  {h}")
        else:
            print("✓ 後端原始碼中未發現殘留 dev_data 資產路徑。")
        if args.report_path:
            Path(args.report_path).write_text(
                json.dumps({"check_only": True, "hits": hits}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return 1 if hits else 0

    # ── Copy mode ───────────────────────────────────────────────────────────────
    print("=" * 60)
    print("資產路徑正規化遷移腳本" + (" [DRY RUN]" if args.dry_run else ""))
    print("=" * 60)

    _ensure_templates_dir(args.dry_run)
    copy_result = _copy_assets(args.dry_run)

    # Post-copy scan
    hits = _scan_hardcoded_devdata(PROJECT_ROOT / "backend")
    if hits:
        print(f"\n⚠  仍有 {len(hits)} 處後端原始碼殘留 dev_data 硬編碼路徑：")
        for h in hits:
            print(f"  {h}")
    else:
        print("\n✓ 後端原始碼中未發現殘留 dev_data 資產路徑。")

    summary = {
        "dry_run": args.dry_run,
        "copied": copy_result["copied"],
        "skipped_src_missing": copy_result["skipped_src_missing"],
        "already_exists": copy_result["already_exists"],
        "residual_hardcoded_hits": hits,
    }

    if args.report_path:
        Path(args.report_path).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[report] 已寫出摘要：{args.report_path}")

    print("\n完成。")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
