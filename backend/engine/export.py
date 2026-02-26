# Export Handler - Facade 整合所有匯出相關功能
"""
ExportHandler

Facade 模式整合所有匯出相關功能：
- excel_exporter.py: Excel 匯出功能
- archive_handler.py: 專案封存 (7z/zip)
"""
import logging
from typing import Optional, Dict, Any
from backend.engine.excel_exporter import ExcelExporter
from backend.engine.archive_handler import ArchiveHandler
from backend.engine.word_exporter import WordExporter

logger = logging.getLogger(__name__)


class ExportHandler:
    """
    Facade 類別，整合所有匯出相關功能。
    """
    
    def __init__(self, project_repo, engine=None):
        self.project_repo = project_repo
        self.engine = engine
        
        # Initialize sub-handlers
        self._excel_exporter = ExcelExporter(project_repo)
        self._archive_handler = ArchiveHandler(project_repo)
        self._word_exporter = WordExporter(project_repo)
    
    # Excel Export Methods
    async def run_excel(self, project_id: str):
        """Export project data to Excel file."""
        return await self._excel_exporter.run_excel(project_id)
    
    async def archive_to_excel(self, project_id: str, excel_name: Optional[str] = None) -> str:
        """Export project jobs data to Excel file."""
        return await self._excel_exporter.archive_to_excel(project_id, excel_name)
    
    # Word Export Methods
    async def run_word(self, project_id: str, template_path: str) -> str:
        """Export project jobs data to Word template file."""
        if not self.engine:
            raise ValueError("Engine instance is required for word export.")
        job_repo = self.engine.get_job_repo(project_id)
        return self._word_exporter.process_export(project_id, template_path, job_repo)
    
    # Archive Methods
    async def seal_project(
        self,
        project_id: str,
        dest_folder: Optional[str] = None,
        include_raw: bool = True,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """Seal (archive) a project to 7z or zip format."""
        return await self._archive_handler.seal_project(
            project_id, dest_folder, include_raw, debug
        )
