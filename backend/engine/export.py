import logging
import os
import time
import json
import shutil
import tempfile
import zipfile
import subprocess
import pandas as pd
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any
from backend.utils.parser import extract_structured_data

logger = logging.getLogger(__name__)

class ExportHandler:
    def __init__(self, project_manager):
        self.project_manager = project_manager

    def run_excel(self, project_id: str):
        try:
            path = self.archive_to_excel(project_id)
            return {"status": "excel_exported", "path": path}
        except Exception as e:
            logger.error(f"Error exporting excel for {project_id}: {e}")
            raise e

    def archive_to_excel(self, project_id: str, excel_name: Optional[str] = None) -> str:
        root = self.project_manager._project_root(project_id)
        if not root.exists():
            raise FileNotFoundError("project root not found")
        db_path = root / "jobs.db"
        if not db_path.exists():
            raise FileNotFoundError("jobs.db not found")

        conn = sqlite3.connect(str(db_path))
        try:
            df_jobs = pd.read_sql_query("SELECT * FROM jobs ORDER BY created_at", conn)
        finally:
            conn.close()

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
            cpu_time = (row.get("ocr_done_at") or 0) - (row.get("ocr_start_at") or 0)
            gpu_time = (row.get("llm_done_at") or 0) - (row.get("llm_start_at") or 0)
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

            # The main text body is always in 'corrected_full_text'
            if "corrected_full_text" in parsed_llm:
                llm_body_text = parsed_llm.get("corrected_full_text")

            # The "人工修正" column is only populated if the status is 'human_correct'
            if job_status == 'human_correct':
                human_correction_text = llm_body_text

            # extract_structured_data handles the {"structured_data": ...} nesting
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
            self.project_manager.update_project_status(project_id, "ARCHIVED")
        except Exception:
            pass

        logger.info("archive_to_excel completed: %s", str(out_path))
        return str(out_path)

    def regenerate_from_archive(
        self, project_id: str, excel_path: str, config: Dict[str, Any]
    ) -> Optional[str]:
        """
        Reads an archived Excel file, uses the '人工修正' column to regenerate LLM output,
        and creates a new archive. The status is updated to 'human_correct'.
        """
        from backend.processing.llm_handler import LLMHandler
        logger.info(f"Starting regeneration for project '{project_id}' from '{excel_path}'")

        root = self.project_manager._project_root(project_id)
        db_path = root / "jobs.db"
        if not db_path.exists():
            logger.error(f"Jobs database not found for project '{project_id}' at '{db_path}'")
            return None

        # --- Read the Excel file ---
        try:
            df = pd.read_excel(excel_path, sheet_name="主表")
            if "人工修正" not in df.columns:
                logger.error(f"Column '人工修正' not found in Excel file '{excel_path}'")
                return None
        except Exception as e:
            logger.error(f"Failed to read Excel file '{excel_path}': {e}")
            return None

        # --- Initialize LLM Handler ---
        try:
            llm_handler = LLMHandler(config=config)
        except Exception as e:
            logger.error(f"Failed to initialize LLMHandler: {e}")
            return None
        
        # --- Process each row ---
        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.cursor()
            for index, row in df.iterrows():
                manual_correction = row.get("人工修正")
                filename = row.get("檔名")

                if pd.isna(manual_correction) or not manual_correction or not filename:
                    # logger.warning(f"Skipping row {index} due to missing '人工修正' text or '檔名'.")
                    continue

                # Find the job_id from the filename
                cursor.execute("SELECT job_id FROM jobs WHERE image_path LIKE ?", (f"%{filename}",))
                job_row = cursor.fetchone()
                if not job_row:
                    logger.warning(f"No job found in database for filename '{filename}'. Skipping.")
                    continue
                
                job_id = job_row[0]
                logger.info(f"Processing job_id '{job_id}' for file '{filename}'...")

                # Regenerate structured data from LLM
                structured_part = llm_handler.regenerate_from_corrected_text(manual_correction)
                
                # Construct the final JSON object in the desired format
                final_json_obj = {
                    "corrected_full_text": manual_correction,
                    "structured_data": structured_part
                }
                final_json_str = json.dumps(final_json_obj, ensure_ascii=False)

                # Update llm_result_json and status in DB
                cursor.execute(
                    "UPDATE jobs SET llm_result_json = ?, status = 'human_correct' WHERE job_id = ?", 
                    (final_json_str, job_id)
                )
            
            conn.commit()
            logger.info("Finished processing all rows from Excel file.")

        finally:
            conn.close()
        
        # --- Re-archive to a new Excel file ---
        new_excel_name = f"{project_id}_regenerated_{int(time.time())}.xlsx"
        logger.info(f"Re-archiving results to '{new_excel_name}'...")
        try:
            new_archive_path = self.archive_to_excel(project_id, excel_name=new_excel_name)
            logger.info(f"Successfully created regenerated archive: {new_archive_path}")
            return new_archive_path
        except Exception as e:
            logger.error(f"Failed to re-archive project: {e}")
            return None

    def seal_project(
        self,
        project_id: str,
        dest_folder: Optional[str] = None,
        include_raw: bool = True,
        debug: bool = False,
    ) -> Dict[str, Any]:
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
