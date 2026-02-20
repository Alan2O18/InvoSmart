# Excel Exporter - Excel 匯出功能
import logging
import os
import time
import json
import tempfile
import pandas as pd
import sqlite3
from pathlib import Path
from typing import Optional
from backend.utils.parser import extract_structured_data

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Handles Excel export functionality."""
    
    def __init__(self, project_repo):
        self.project_repo = project_repo
    
    def run_excel(self, project_id: str):
        """Export project data to Excel file."""
        try:
            path = self.archive_to_excel(project_id)
            return {"status": "excel_exported", "path": path}
        except Exception as e:
            logger.error(f"Error exporting excel for {project_id}: {e}")
            raise e

    def archive_to_excel(self, project_id: str, excel_name: Optional[str] = None) -> str:
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
        from backend.repositories.job_repository import JobRepository
        job_repo = JobRepository(project_id)
        jobs_list = job_repo.list_jobs()
        
        if not jobs_list:
            raise FileNotFoundError("No jobs found for this project")
        
        df_jobs = pd.DataFrame(jobs_list)

        # Define new column layout
        main_cols = [
            "狀態",
            "檔名",
            "來源檔案(位置)",
            "CPU處理時間",
            "GPU處理時間",
            "總時間",
            "備註",
            "檔案日期",
            "供應商",
            "金額",
            "人工修正",
            "LLM結果本文",
            "RAW_OCR",
        ]
        main_rows = []
        detail_rows = []

        for _, row in df_jobs.iterrows():
            filename = (
                row.get("image_path") and Path(row.get("image_path")).name or None
            )
            
            # Parse stats from JSON fields
            cpu_time = 0
            gpu_time = 0
            try:
                ocr_stats = row.get("ocr_stats")
                if ocr_stats:
                    ocr_stats_data = json.loads(ocr_stats) if isinstance(ocr_stats, str) else ocr_stats
                    cpu_time = ocr_stats_data.get("total_time_s", 0)
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                llm_stats = row.get("llm_stats")
                if llm_stats:
                    llm_stats_data = json.loads(llm_stats) if isinstance(llm_stats, str) else llm_stats
                    # llm_stats is an array, sum up all stages
                    if isinstance(llm_stats_data, list):
                        gpu_time = sum(s.get("total_time_s", 0) for s in llm_stats_data)
                    else:
                        gpu_time = llm_stats_data.get("total_time_s", 0)
            except (json.JSONDecodeError, TypeError):
                pass
            
            total = None
            try:
                if row.get("created_at") and row.get("updated_at"):
                    total = float(row.get("updated_at")) - float(row.get("created_at"))
            except Exception:
                total = None

            raw_llm = row.get("llm_result_json")
            raw_ocr = row.get("ocr_result_json")
            job_status = row.get("status")

            human_correction_text = None
            llm_body_text = None
            
            # Parse LLM JSON to extract multiple pieces of information
            parsed_llm = {}
            if isinstance(raw_llm, str) and raw_llm.strip():
                try:
                    parsed_llm = json.loads(raw_llm)
                except json.JSONDecodeError:
                    parsed_llm = {}

            # Generate text from flat structure or use existing text
            llm_body_text = self._generate_text_from_llm_result(parsed_llm)

            # The "人工修正" column is only populated if the status is 'human_correct'
            if job_status == 'human_correct':
                human_correction_text = llm_body_text

            # extract_structured_data handles flat structure
            structured = extract_structured_data(raw_llm)
            if not structured and isinstance(raw_ocr, str) and raw_ocr.strip():
                structured = extract_structured_data(raw_ocr)

            supplier = structured.get("supplier", "")
            total_amount = structured.get("total_amount", "")
            file_date = (
                structured.get("date", "") or structured.get("invoice_date", "") or ""
            )

            main_rows.append(
                {
                    "狀態": job_status,
                    "檔名": filename,
                    "來源檔案(位置)": row.get("image_path"),
                    "CPU處理時間": cpu_time,
                    "GPU處理時間": gpu_time,
                    "總時間": total,
                    "備註": None,
                    "檔案日期": file_date,
                    "供應商": supplier,
                    "金額": total_amount,
                    "人工修正": human_correction_text,
                    "LLM結果本文": llm_body_text,
                    "RAW_OCR": raw_ocr,
                }
            )

            # 細項：取 structured["items"]
            items = structured.get("items") or []
            for it in items:
                detail_rows.append(
                    {
                        "檔名": filename,
                        "品項描述": it.get("description"),
                        "數量": it.get("quantity"),
                        "金額": it.get("price"),
                    }
                )

        df_main = pd.DataFrame(main_rows, columns=main_cols)
        df_detail = pd.DataFrame(
            detail_rows, columns=["檔名", "品項描述", "數量", "金額"]
        )

        ts = int(time.time())
        excel_name = excel_name or f"{project_id}_archive_{ts}.xlsx"
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
            self.project_repo.update_project_status(project_id, "ARCHIVED")
        except Exception:
            pass

        logger.info("archive_to_excel completed: %s", str(out_path))
        return str(out_path)
    
    def _generate_text_from_llm_result(self, parsed_llm: dict) -> str:
        """從扁平 LLM 結果生成文字摘要"""
        if not parsed_llm:
            return ""
        
        lines = []
        
        header = parsed_llm.get("header", {})
        if header.get("supplier"):
            lines.append(f"# {header['supplier']}")
        if header.get("invoice_id"):
            lines.append(f"發票號碼: {header['invoice_id']}")
        if header.get("date"):
            lines.append(f"日期: {header['date']}")
        
        items = parsed_llm.get("items", [])
        if items:
            lines.append("")
            lines.append("| 品名 | 數量 | 單價 | 小計 |")
            lines.append("|------|------|------|------|")
            for item in items:
                name = item.get("name", item.get("description", ""))
                qty = item.get("qty", item.get("quantity", ""))
                price = item.get("price", "")
                total = item.get("total", "")
                lines.append(f"| {name} | {qty} | {price} | {total} |")
        
        summary = parsed_llm.get("summary", {})
        if summary.get("total"):
            lines.append("")
            lines.append(f"**合計**: {summary['total']}")
        
        return "\n".join(lines)
