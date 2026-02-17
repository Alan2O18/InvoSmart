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

logger = logging.getLogger(__name__)


class ReceiptProcessor:
    """
    收據處理器 (VLM-First 架構)
    
    極簡化流程：VLM → QR 驗證 → 邏輯驗算
    """
    
    def __init__(self, config: dict):
        """初始化處理器"""
        self.config = config
        
        # 核心模組 (僅保留 3 個)
        self.vision_handler = VisionHandler(config)
        self.qr_handler = QRHandler(config)
        self.validator = PythonValidator(config)
        
        logger.info("ReceiptProcessor 初始化完成 (VLM-First 架構)")
    
    def update_config(self, config: dict):
        """更新配置"""
        self.config = config
        # Propagate to sub-handlers
        self.vision_handler.update_config(config)
        # QRHandler and Validator might not need updates usually, but can be added if needed
        # self.qr_handler.update_config(config) 
        # self.validator.update_config(config)
        logger.info("[ReceiptProcessor] 配置已更新")
    
    def process(self, image_array: np.ndarray) -> dict:
        """
        處理收據圖片 - 單一入口點
        
        Args:
            image_array: OpenCV 格式的圖片 (BGR)
            
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
        
        # ===== Step 1: VLM 分析 =====
        logger.info("[Step 1] VLM 分析...")
        vlm_result, vlm_stats = self.vision_handler.process_image(image_array)
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
        合併 QR Code 資料到 VLM 結果
        
        QR Code 為確定性資料，優先信任。
        """
        if not vlm_result.get("header"):
            vlm_result["header"] = {}
        
        header = vlm_result["header"]
        
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
        if not vlm_result.get("verification"):
            vlm_result["verification"] = {}
        vlm_result["verification"]["qr_verified"] = True
        
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
