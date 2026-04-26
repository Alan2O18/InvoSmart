# Excel Exporter - Excel 匯出功能
import logging
import os
import time
import json
import tempfile
import re
import pandas as pd
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional
from backend.utils.parser import extract_structured_data

logger = logging.getLogger(__name__)
from backend.repositories.job_repository import JobRepository



class ExcelExporter:
    """Handles Excel export functionality."""
    
    def __init__(self, project_repo):
        self.project_repo = project_repo

    @staticmethod
    def _sanitize_windows_filename_fragment(value: str) -> str:
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", value or "")
        return sanitized.strip()
    
    async def run_excel(self, project_id: str):
        """Export project data to Excel file."""
        try:
            path = await self.archive_to_excel(project_id)
            return {"status": "excel_exported", "path": path}
        except Exception as e:
            logger.error(f"Error exporting excel for {project_id}: {e}")
            raise e

    async def archive_to_excel(self, project_id: str, excel_name: Optional[str] = None) -> str:
        """
        Export project jobs data to Excel file with main table and details table.
        
        Args:
            project_id: Project identifier
            excel_name: Optional custom Excel filename
            
        Returns:
            Path to the created Excel file
        """
        root = self.project_repo._project_root(project_id)
        if not root.exists():
            raise FileNotFoundError("project root not found")

        # 從全域集中資料庫讀取 (透過 JobRepository)
        from backend.database.core import AsyncSessionLocal
        job_repo = JobRepository(project_id, session_factory=AsyncSessionLocal)
        base_jobs_list = await job_repo.list_jobs()
        
        if not base_jobs_list:
            raise FileNotFoundError("No jobs found for this project")
            
        jobs_list = []
        for b_job in base_jobs_list:
            job_data = await job_repo.get_job(b_job["job_id"])
            if job_data:
                jobs_list.append(job_data)
        
        df_jobs = pd.DataFrame(jobs_list)

        # Define new column layout
        main_cols = [
            "狀態",
            "檔名",
            "來源檔案(位置)",
            "VLM處理時間",
            "總時間",
            "備註",
            "檔案日期",
            "供應商",
            "金額",
            "人工修正",
            "VLM結果本文",
        ]
        main_rows = []
        detail_rows = []

        for _, row in df_jobs.iterrows():
            job_id = row.get("job_id")
            filename = (
                row.get("image_path") and Path(row.get("image_path")).name or None
            )
            
            # Parse stats from JSON fields
            vlm_time = 0
            try:
                vlm_stats = row.get("vlm_stats")
                if vlm_stats:
                    vlm_stats_data = json.loads(vlm_stats) if isinstance(vlm_stats, str) else vlm_stats
                    vlm_time = vlm_stats_data.get("total_time_s", 0)
            except (json.JSONDecodeError, TypeError):
                pass
            
            total = None
            try:
                if row.get("created_at") and row.get("updated_at"):
                    total = float(row.get("updated_at")) - float(row.get("created_at"))
            except Exception:
                total = None

            raw_vlm = row.get("vlm_result_json")
            job_status = row.get("status")

            human_correction_text = None
            vlm_body_text = None

            display_result = {}
            if job_id:
                try:
                    display_result = await job_repo.get_display_result(job_id) or {}
                except Exception:
                    display_result = {}
            
            # Parse VLM JSON to extract multiple pieces of information
            parsed_vlm = {}
            if isinstance(display_result, dict) and display_result:
                parsed_vlm = display_result
            elif isinstance(raw_vlm, str) and raw_vlm.strip():
                try:
                    parsed_vlm = json.loads(raw_vlm)
                except json.JSONDecodeError:
                    parsed_vlm = {}

            # Generate text from flat structure
            vlm_body_text = self._generate_text_from_vlm_result(parsed_vlm)

            # extract_structured_data handles flat structure
            # Priority: display_result > vlm_result_json
            structured = extract_structured_data(display_result)
            if not structured:
                structured = extract_structured_data(raw_vlm)

            supplier = structured.get("supplier") or row.get("supplier", "")
            total_amount = structured.get("total_amount")
            if total_amount in (None, ""):
                total_amount = row.get("total_amount", "")
            file_date = (
                structured.get("date", "")
                or structured.get("invoice_date", "")
                or row.get("invoice_date", "")
                or ""
            )

            main_rows.append(
                {
                    "狀態": job_status,
                    "檔名": filename,
                    "來源檔案(位置)": row.get("image_path"),
                    "VLM處理時間": vlm_time,
                    "總時間": total,
                    "備註": None,
                    "檔案日期": file_date,
                    "供應商": supplier,
                    "金額": total_amount,
                    "人工修正": human_correction_text,
                    "VLM結果本文": vlm_body_text,
                }
            )

            # 細項：取 structured["items"]
            items = structured.get("items") or []
            for it in items:
                detail_rows.append(
                    {
                        "狀態": job_status,
                        "檔名": filename,
                        "來源檔案(位置)": row.get("image_path"),
                        "專案": project_id,
                        "發票號碼": structured.get("invoice_id", "") or structured.get("voucher_id", "") or row.get("voucher_id", ""),
                        "供應商": supplier,
                        "報帳名目": it.get("category", ""),
                        "品項名稱": it.get("description", ""),
                        "數量": it.get("quantity", ""),
                        "單價": it.get("price", ""),
                        "小計": it.get("total", ""),
                    }
                )

        df_main = pd.DataFrame(main_rows, columns=main_cols)
        df_detail = pd.DataFrame(
            detail_rows, columns=[
                "狀態", "檔名", "來源檔案(位置)", "專案", "發票號碼", "供應商", 
                "報帳名目", "品項名稱", "數量", "單價", "小計"
            ]
        )

        if not excel_name:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            project = await self.project_repo.get_project(project_id)
            project_name = ""
            if isinstance(project, dict):
                project_name = str(project.get("name") or "")
                if not project_name:
                    project_name = str((project.get("metadata") or {}).get("name") or "")

            safe_project_id = self._sanitize_windows_filename_fragment(project_id) or "UNKNOWN"
            safe_project_name = self._sanitize_windows_filename_fragment(project_name) or "未命名"
            excel_name = f"{safe_project_id}「{safe_project_name}」_預結算表_{ts}.xlsx"
        out_path = root / excel_name

        # 選 engine: 優先 xlsxwriter，再 openpyxl；都沒有就 fallback CSV
        engine = None
        try:
            import xlsxwriter  # type: ignore
            engine = "xlsxwriter"
        except Exception:
            try:
                import openpyxl  # type: ignore
                engine = "openpyxl"
            except Exception:
                engine = None

        fd, tmp = tempfile.mkstemp(dir=str(out_path.parent))
        os.close(fd)
        try:
            if engine:
                with pd.ExcelWriter(tmp, engine=engine) as writer:
                    df_main.to_excel(writer, sheet_name="主表", index=False)
                    df_detail.to_excel(writer, sheet_name="細項表", index=False)
                os.replace(tmp, str(out_path))
            else:
                # fallback: 兩個 CSV（放在同一 folder，並改名）
                csv_main = str(out_path.with_suffix(".main.csv"))
                csv_detail = str(out_path.with_suffix(".detail.csv"))
                df_main.to_csv(csv_main, index=False)
                df_detail.to_csv(csv_detail, index=False)
                os.unlink(tmp)
                logger.warning(
                    "No Excel engine found; exported CSV instead: %s, %s",
                    csv_main,
                    csv_detail,
                )
                out_path = Path(csv_main)  # 回傳其中一個路徑作為代表
        except Exception as e:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise

        # 更新全域狀態
        try:
            await self.project_repo.update_project_status(project_id, "ARCHIVED")
        except Exception:
            pass

        logger.info("archive_to_excel completed: %s", str(out_path))
        return str(out_path)
    
    def _generate_text_from_vlm_result(self, parsed_vlm: dict) -> str:
        """從扁平 VLM 結果生成文字摘要"""
        if not parsed_vlm:
            return ""
        
        lines = []
        
        header = parsed_vlm.get("header", {})
        if header.get("supplier"):
            lines.append(f"# {header['supplier']}")
        if header.get("invoice_id"):
            lines.append(f"發票號碼: {header['invoice_id']}")
        if header.get("date"):
            lines.append(f"日期: {header['date']}")
        
        items = parsed_vlm.get("items", [])
        if items:
            lines.append("")
            lines.append("| 名目 | 單價 | 數量 | 小計 | 品名 |")
            lines.append("|------|------|------|------|------|")
            for item in items:
                cat = item.get("category", "")
                price = item.get("price", "")
                qty = item.get("qty", item.get("quantity", ""))
                total = item.get("total", "")
                name = item.get("name", item.get("description", ""))
                lines.append(f"| {cat} | {price} | {qty} | {total} | {name} |")
        
        summary = parsed_vlm.get("summary", {})
        if summary.get("total"):
            lines.append("")
            lines.append(f"**合計**: {summary['total']}")
        
        return "\n".join(lines)
