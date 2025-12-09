# Regeneration Handler - 人工修正重新生成功能
import logging
import time
import json
import sqlite3
import pandas as pd
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class RegenerationHandler:
    """Handles regeneration of LLM results from human corrections."""
    
    def __init__(self, project_manager, excel_exporter):
        self.project_manager = project_manager
        self.excel_exporter = excel_exporter
    
    def regenerate_from_archive(
        self, project_id: str, excel_path: str, config: Dict[str, Any]
    ) -> Optional[str]:
        """
        Reads an archived Excel file, uses the '人工修正' column to regenerate LLM output,
        and creates a new archive. The status is updated to 'human_correct'.
        
        Args:
            project_id: Project identifier
            excel_path: Path to the archived Excel file
            config: LLM handler configuration
            
        Returns:
            Path to the new archive, or None on failure
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
            new_archive_path = self.excel_exporter.archive_to_excel(project_id, excel_name=new_excel_name)
            logger.info(f"Successfully created regenerated archive: {new_archive_path}")
            return new_archive_path
        except Exception as e:
            logger.error(f"Failed to re-archive project: {e}")
            return None
