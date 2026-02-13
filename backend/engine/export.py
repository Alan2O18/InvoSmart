# Export Handler - Facade 整合所有匯出相關功能
"""
ExportHandler

Facade 模式整合所有匯出相關功能：
- excel_exporter.py: Excel 匯出功能
- archive_handler.py: 專案封存 (7z/zip)
- regeneration_handler.py: 人工校正重新生成
"""
import logging
from typing import Optional, Dict, Any
from backend.engine.excel_exporter import ExcelExporter
from backend.engine.archive_handler import ArchiveHandler
from backend.engine.regeneration_handler import RegenerationHandler

logger = logging.getLogger(__name__)


class ExportHandler:
    """
    Facade 類別，整合所有匯出相關功能。
    """
    
    def __init__(self, project_repo):
        self.project_repo = project_repo
        
        # Initialize sub-handlers
        self._excel_exporter = ExcelExporter(project_repo)
        self._archive_handler = ArchiveHandler(project_repo)
        self._regeneration_handler = RegenerationHandler(
            project_repo, self._excel_exporter
        )
    
    # Excel Export Methods
    def run_excel(self, project_id: str):
        """Export project data to Excel file."""
        return self._excel_exporter.run_excel(project_id)
    
    def archive_to_excel(self, project_id: str, excel_name: Optional[str] = None) -> str:
        """Export project jobs data to Excel file."""
        return self._excel_exporter.archive_to_excel(project_id, excel_name)
    
    # Regeneration Methods
    def regenerate_from_archive(
        self, project_id: str, excel_path: str, config: Dict[str, Any]
    ) -> Optional[str]:
        """Regenerate LLM results from human corrections in archived Excel."""
        return self._regeneration_handler.regenerate_from_archive(
            project_id, excel_path, config
        )
    
    # Archive Methods
    def seal_project(
        self,
        project_id: str,
        dest_folder: Optional[str] = None,
        include_raw: bool = True,
        debug: bool = False,
    ) -> Dict[str, Any]:
        """Seal (archive) a project to 7z or zip format."""
        return self._archive_handler.seal_project(
            project_id, dest_folder, include_raw, debug
        )
