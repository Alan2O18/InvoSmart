# backend/processing/receipt_processor.py
"""
收據處理器 v3 - VLM-First 簡化架構

流程：
1. VLM 識別 (Gemini Flash Lite) → 直接輸出結構化 JSON
2. QR Code 掃描 → 輔助驗證電子發票
3. Python 驗算 → 信心度評估
"""
import logging
import json
import time
import numpy as np
from typing import Optional, Dict, Any
from pathlib import Path

from backend.processing.python_validator import PythonValidator
from backend.processing.qr_handler import QRHandler
from backend.processing.vision_handler import VisionHandler
from backend.repositories.suggestion_repository import SuggestionRepository

logger = logging.getLogger(__name__)


class ReceiptProcessor:
    """
    收據處理器 (VLM-First 架構)
    
    極簡化流程：RAG Context → VLM → QR 驗證 → 邏輯驗算
    """
    
    def __init__(self, config: dict, db_path=None):
        """初始化處理器"""
        self.config = config
        
        # 核心模組
        self.vision_handler = VisionHandler(config)
        self.qr_handler = QRHandler(config)
        self.validator = PythonValidator(config)

        # Init repos
        from backend.repositories.suggestion_repository import SuggestionRepository
        from backend.repositories.project_repository import ProjectRepository
        from backend.database.core import AsyncSessionLocal
        self.suggestion_repo = SuggestionRepository(session_factory=AsyncSessionLocal)
        try:
            self.project_repo = ProjectRepository(config=self.config, session_factory=AsyncSessionLocal)
        except Exception:
            self.project_repo = None
        
        logger.info("ReceiptProcessor 初始化完成 (VLM-First 架構)")
    
    def update_config(self, config: dict):
        """更新配置"""
        self.config = config
        self.vision_handler.update_config(config)
        logger.info("[ReceiptProcessor] 配置已更新")
    
    def process(self, image_array: np.ndarray, project_id: str = None) -> dict:
        """
        處理收據圖片 - 單一入口點
        
        Args:
            image_array: OpenCV 格式的圖片 (BGR)
            project_id: 專案 ID，用於獲取預算品類限制 (選填)
            
        Returns:
            dict: 處理結果，包含:
                - success: bool
                - result: 結構化收據資料 (header, items, summary)
                - metadata: 處理統計資訊
        """
        start_time = time.time()
        logger.info("="*50)
        logger.info("[Pipeline] 開始收據處理流程 (VLM-First)")
        
        stats_list = []
        
        # ===== Step 0: 建立 RAG 上下文與預算品類限制 =====
        rag_context = ""
        budget_categories = []
        if project_id and self.project_repo:
            try:
                import asyncio
                import inspect
                res = self.project_repo.get_project(project_id)
                if inspect.iscoroutine(res):
                    try:
                        loop = asyncio.get_running_loop()
                        proj = loop.run_until_complete(res)
                    except RuntimeError:
                        proj = asyncio.run(res)
                else:
                    proj = res
                
                if proj and isinstance(proj, dict):
                    meta = proj.get("metadata") or {}
                    budget_exp = meta.get("budgetExpense") or []
                    for item in budget_exp:
                        if isinstance(item, dict) and item.get("name"):
                            name = str(item["name"]).strip()
                            if name and name not in budget_categories:
                                budget_categories.append(name)
            except Exception as e:
                logger.warning(f"[Step 0] 獲取專案預算品類失敗: {e}")

        try:
            import asyncio
            import inspect
            res = self.suggestion_repo.build_rag_context()
            if inspect.iscoroutine(res):
                try:
                    loop = asyncio.get_running_loop()
                    # If there's a running loop, we shouldn't use asyncio.run
                    rag_context = loop.run_until_complete(res)
                except RuntimeError:
                    # No running loop, use asyncio.run
                    rag_context = asyncio.run(res)
            else:
                rag_context = res
                
            if rag_context:
                logger.info(f"[Step 0] RAG 上下文已建立 ({len(rag_context)} chars)")
            else:
                logger.info("[Step 0] 建議詞庫尚無資料，跳過 RAG 注入")
        except Exception as e:
            logger.warning(f"[Step 0] 建立 RAG 上下文失敗（不影響辨識）: {e}")

        if budget_categories:
            cat_list_str = "、".join(budget_categories)
            category_restriction = (
                f"\n\n【限制與品類規範】\n"
                f"這張發票的品項分類（items 陣列中每個項目的 category 欄位），必須只能從以下專案預算之品類列表中選擇，"
                f"絕對不可自行發明或填寫列表外的品類。若無法完全歸類，請優先選擇最接近的品類：\n"
                f"▸ 允許的品類列表：{cat_list_str}\n"
            )
            rag_context = category_restriction + "\n" + rag_context
            logger.info(f"[Step 0] 已注入預算品類限制，共 {len(budget_categories)} 個品類")
        
        # ===== Step 1: VLM 分析 (含 RAG 上下文) =====
        logger.info("[Step 1] VLM 分析...")
        vlm_result, vlm_stats = self.vision_handler.process_image(image_array, prompt_context=rag_context)
        stats_list.append(vlm_stats)
        
        if "error" in vlm_stats:
            logger.error(f"[Step 1] VLM 分析失敗: {vlm_stats['error']}")
            return self._create_error_result(vlm_stats['error'], stats_list)
        
        logger.info(f"[Step 1] VLM 完成，耗時 {vlm_stats.get('total_time_s', 0):.2f}s")
        
        # ===== Step 2: QR Code 輔助驗證 =====
        logger.info("[Step 2] QR Code 掃描...")
        qr_data = self.qr_handler.detect_and_decode(image_array)
        
        if qr_data:
            logger.info(f"[Step 2] QR Code 偵測成功: {qr_data.get('invoice_id', 'N/A')}")
            vlm_result = self._merge_qr_data(vlm_result, qr_data)
        else:
            logger.info("[Step 2] 未偵測到 QR Code")
        
        # ===== Step 3: 邏輯驗算 =====
        logger.info("[Step 3] 邏輯驗算...")
        validation = self.validator.validate(vlm_result)
        
        logger.info(f"[Step 3] 驗算完成: valid={validation.is_valid}, confidence={validation.confidence:.2f}")
        if validation.issues:
            logger.warning(f"[Step 3] 發現問題: {validation.issues}")
        
        # ===== 組裝結果 =====
        total_time = time.time() - start_time
        logger.info(f"[Pipeline] 處理完成，總耗時 {total_time:.2f}s")
        
        return {
            "success": True,
            "result": vlm_result,
            "validation": {
                "is_valid": validation.is_valid,
                "confidence": validation.confidence,
                "issues": validation.issues
            },
            "metadata": {
                "total_time_s": round(total_time, 3),
                "qr_detected": qr_data is not None,
                "stats": stats_list
            }
        }
    
    def _merge_qr_data(self, vlm_result: dict, qr_data: dict) -> dict:
        """
        合併 QR Code 資料到 VLM 結果，並備份原始資料以進行二次對帳。
        
        QR Code 為確定性資料，優先信任。
        """
        if not vlm_result.get("header"):
            vlm_result["header"] = {}
        
        header = vlm_result["header"]
        
        if not vlm_result.get("verification"):
            vlm_result["verification"] = {}
        verification = vlm_result["verification"]
        
        # 備份 VLM 原始辨識結果以供二次對帳
        verification["vlm_invoice_id"] = header.get("invoice_id") or ""
        verification["vlm_date"] = header.get("date") or ""
        verification["vlm_total"] = vlm_result.get("summary", {}).get("total") if vlm_result.get("summary") else None
        
        # 保存 QR 資料供對照
        verification["qr_invoice_id"] = qr_data.get("invoice_id") or ""
        verification["qr_date"] = qr_data.get("date") or ""
        verification["qr_total"] = qr_data.get("total")

        # QR 資料優先覆蓋 (若存在)
        if qr_data.get("invoice_id"):
            header["invoice_id"] = qr_data["invoice_id"]
        if qr_data.get("date"):
            header["date"] = qr_data["date"]
        if qr_data.get("total"):
            if not vlm_result.get("summary"):
                vlm_result["summary"] = {}
            vlm_result["summary"]["total"] = qr_data["total"]
        
        # 標記 QR 驗證
        verification["qr_verified"] = True
        
        return vlm_result
    
    def _create_error_result(self, error: str, stats: list) -> dict:
        """建立錯誤結果"""
        return {
            "success": False,
            "error": error,
            "result": {},
            "metadata": {
                "stats": stats
            }
        }


# 測試用
if __name__ == "__main__":
    import sys
    from backend import utils
    
    if len(sys.argv) < 2:
        print("Usage: python receipt_processor.py <image_path>")
        sys.exit(1)
    
    # 載入配置
    config = utils.load_config()
    image = utils.cv_imread_chinese(sys.argv[1])
    
    # 處理
    processor = ReceiptProcessor(config)
    result = processor.process(image)
    
    print("\n處理結果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
