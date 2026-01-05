# backend/processing/receipt_processor.py
"""
收據處理器 v2 - 整合所有處理流程

流程：
1. OCR 識別 (RapidOCR)
2. 關鍵字分類 → 判斷收據類型
3A. 電子發票 → QR Code 掃描
3B. 手寫收據 → qwen3-vl:2b VLM
3C. 其他收據 → qwen3:1.7b LLM
4. Python 驗算
5A. 通過 → 高信心結果
5B. 異常 → gemma3:4b 修正
"""
import logging
import json
import re
import numpy as np
from typing import Optional

from backend.processing.keyword_classifier import KeywordClassifier, ReceiptType
from backend.processing.python_validator import PythonValidator
from backend.processing.rapidocr_handler import RapidOCRHandler
from backend.processing.qr_handler import QRHandler
from backend.processing.vision_handler import VisionHandler
from backend.processing.llm_handler import LLMHandler
from backend.processing.gemma_corrector import GemmaCorrector

logger = logging.getLogger(__name__)


class ReceiptProcessorV2:
    """
    收據處理器 v2
    
    整合 OCR、分類、VLM/LLM、驗算、修正等完整流程
    """
    
    def __init__(self, config: dict):
        """初始化所有處理器"""
        self.config = config
        
        # 初始化各模組
        self.ocr_handler = RapidOCRHandler(config)
        self.classifier = KeywordClassifier(config)
        self.qr_handler = QRHandler(config)
        self.vision_handler = VisionHandler(config)
        self.llm_handler = LLMHandler(config)
        self.validator = PythonValidator(config)
        self.gemma_corrector = GemmaCorrector(config)
        
        logger.info("ReceiptProcessorV2 初始化完成")
    
    def process(self, image_array: np.ndarray) -> dict:
        """
        處理收據圖片
        
        Args:
            image_array: OpenCV 格式的圖片
            
        Returns:
            dict: 處理結果，包含 ocr_result, ocr_stats, llm_result, llm_stats 等
        """
        import time
        logger.info("="*50)
        logger.info("[Pipeline] 開始收據處理流程")
        
        # 用於收集 LLM 處理統計
        llm_stats = []
        
        # ===== Step 1: OCR =====
        logger.info("[Step 1] 執行 OCR...")
        ocr_result, ocr_stats = self.ocr_handler.do_ocr(image_array)
        ocr_text = self.ocr_handler.to_plain_text(ocr_result)
        logger.info(f"[Step 1] OCR 完成，共 {len(ocr_result)} 個區塊，{len(ocr_text)} 字元，耗時 {ocr_stats.get('total_time_s', 0)}s")
        
        # ===== Step 2: 關鍵字分類 =====
        logger.info("[Step 2] 關鍵字分類...")
        
        # 同時嘗試掃描 QR Code
        qr_data = self.qr_handler.detect_and_decode(image_array)
        has_qr = qr_data is not None
        
        classification = self.classifier.classify(ocr_text, has_qr_code=has_qr)
        receipt_type = classification.receipt_type
        logger.info(f"[Step 2] 分類結果: {receipt_type.value} (信心度: {classification.confidence:.2f})")
        logger.debug(f"[Step 2] 匹配關鍵字: {classification.matched_keywords}")
        
        # ===== Step 3: 分流處理 =====
        logger.info(f"[Step 3] 分流處理: {receipt_type.value}")
        
        extraction_start = time.time()
        if receipt_type == ReceiptType.ELECTRONIC:
            # 3A: 電子發票 - 使用 QR Code 資料
            extracted_data = self._process_electronic(qr_data)
        elif receipt_type == ReceiptType.HANDWRITTEN:
            # 3B: 手寫收據 - 使用 VLM
            extracted_data, vlm_stats = self._process_handwritten(image_array)
            # 使用 VLM 返回的詳細 stats
            if vlm_stats:
                vlm_stats["stage"] = "vlm_extraction"
                llm_stats.append(vlm_stats)
        else:
            # 3C: 其他收據 - 使用 LLM 處理 OCR 結果
            extracted_data, stats = self._process_other(ocr_text)
            if stats:
                stats["stage"] = "llm_extraction"
                llm_stats.append(stats)
        
        if not extracted_data:
            logger.warning("[Step 3] 提取失敗，返回空結果")
            return self._create_error_result(receipt_type, "資料提取失敗", ocr_result, ocr_stats)
        
        # ===== Step 4: Python 驗算 =====
        logger.info("[Step 4] Python 驗算...")
        validation = self.validator.validate(extracted_data)
        logger.info(f"[Step 4] 驗算結果: {'通過' if validation.is_valid else '有問題'}")
        
        if validation.issues:
            logger.warning(f"[Step 4] 發現問題: {validation.issues}")
        
        # ===== Step 5: GEMMA 修正 =====
        was_corrected = False
        correction_failed = False
        gemma_correction = None
        
        if not validation.is_valid:
            logger.info(f"[Step 5] 嘗試使用 GEMMA3 修正... (共 {len(validation.issues)} 個問題)")
            
            # 調用 GEMMA
            correction_result = self.gemma_corrector.correct(
                image_array=image_array,
                original_result=extracted_data,
                issues=validation.issues
            )
            
            if correction_result.get("success"):
                extracted_data = correction_result.get("data", extracted_data)
                was_corrected = True
                gemma_correction = correction_result.get("correction")
                
                # 記錄統計
                if "correction_time" in correction_result:
                    llm_stats.append({
                        "processor": "gemma3:4b",
                        "stage": "correction",
                        "time_s": round(correction_result["correction_time"], 2),
                        "issues_count": len(validation.issues)
                    })
                
                logger.info(f"[Step 5] 修正成功，耗時 {correction_result.get('correction_time', 0):.2f}s")
                
                # 重新驗算以更新信心度
                validation = self.validator.validate(extracted_data)
                logger.info(f"[Step 5] 修正後驗算: {'通過' if validation.is_valid else '仍有問題'}")
                
            else:
                correction_failed = True
                logger.warning(f"[Step 5] 修正失敗: {correction_result.get('error')}")

        # ===== Step 6: 返回結果 =====
        logger.info(f"[Step 6] 返回結果（最終驗算{'通過' if validation.is_valid else '有問題'}）")
        return self._create_success_result(
            receipt_type=receipt_type,
            data=extracted_data,
            confidence=validation.confidence,
            issues=validation.issues,
            ocr_raw=ocr_result,
            ocr_stats=ocr_stats,
            llm_stats=llm_stats,
            was_corrected=was_corrected,
            correction_failed=correction_failed,
            gemma_correction=gemma_correction
        )

    def process_ocr_only(self, image_array: np.ndarray) -> dict:
        """
        僅執行 OCR 和分類（不進行進階提取）
        
        Args:
            image_array: OpenCV 格式的圖片
            
        Returns:
            dict: 包含 ocr_result, ocr_stats, invoice_type
        """
        logger.info("="*50)
        logger.info("[Pipeline] 開始 OCR-only 處理")
        
        # ===== Step 1: OCR =====
        logger.info("[Step 1] 執行 OCR...")
        ocr_result, ocr_stats = self.ocr_handler.do_ocr(image_array)
        ocr_text = self.ocr_handler.to_plain_text(ocr_result)
        logger.info(f"[Step 1] OCR 完成")
        
        # ===== Step 2: 關鍵字分類 =====
        logger.info("[Step 2] 關鍵字分類...")
        qr_data = self.qr_handler.detect_and_decode(image_array)
        has_qr = qr_data is not None
        
        classification = self.classifier.classify(ocr_text, has_qr_code=has_qr)
        receipt_type = classification.receipt_type
        logger.info(f"[Step 2] 分類結果: {receipt_type.value}")
        
        # 建立 OCR result
        RECEIPT_TYPE_CHINESE = {
            ReceiptType.ELECTRONIC: "電子發票",
            ReceiptType.HANDWRITTEN: "免用統一發票收據",
            ReceiptType.OTHER: "其他收據",
            ReceiptType.UNKNOWN: "其他收據"
        }
        receipt_type_chinese = RECEIPT_TYPE_CHINESE.get(receipt_type, "其他收據")
        
        ocr_result_formatted = {
            "text": ocr_text,
            "type": receipt_type_chinese
        }
        
        return {
            "success": True,
            "invoice_type": receipt_type.value,
            "ocr_result": ocr_result_formatted,
            "ocr_stats": ocr_stats
        }
    
    def _process_electronic(self, qr_data: dict) -> dict:
        """處理電子發票 - 從 QR Code 提取"""
        logger.debug("[3A] 處理電子發票...")
        
        if not qr_data or not qr_data.get("success"):
            return {}
        
        # QR 資料已經是結構化的，轉換為標準格式
        data = qr_data.get("data", {})
        return {
            "receipt_type": "電子發票",
            "header": {
                "supplier": data.get("seller_id", ""),
                "invoice_id": data.get("invoice_id", ""),
                "date": data.get("invoice_date", ""),
                "tax_id": data.get("seller_id", "")
            },
            "items": [],  # 電子發票 QR 通常不包含品項明細
            "summary": {
                "total": data.get("total", 0)
            },
            "verification": {}
        }
    
    def _process_handwritten(self, image_array: np.ndarray) -> tuple:
        """處理手寫收據 - 使用 VLM
        
        Returns:
            tuple: (extracted_data, vlm_stats)
        """
        logger.debug("[3B] 處理手寫收據...")
        
        raw_output, vlm_stats = self.vision_handler.process_handwritten(image_array)
        
        if not raw_output:
            return {}, vlm_stats
        
        # 解析 JSON
        return self._parse_json_from_text(raw_output), vlm_stats
    
    def _process_other(self, ocr_text: str) -> tuple:
        """處理其他收據 - 使用 LLM"""
        logger.debug("[3C] 處理其他收據...")
        
        # 構建 prompt
        prompt = f"""請將以下 OCR 識別的文字轉換為標準 JSON 格式。

【OCR 文字】
{ocr_text}

【JSON 結構】
{{
    "receipt_type": "發票類型",
    "header": {{
        "supplier": "商家名稱",
        "invoice_id": "發票號碼",
        "date": "YYYY-MM-DD",
        "tax_id": "統一編號"
    }},
    "items": [
        {{ "name": "品名", "qty": 1, "price": 100, "total": 100 }}
    ],
    "summary": {{
        "total": 100
    }}
}}

請直接輸出 JSON。"""
        
        # 調用 LLM（啟用思考模式）
        raw_output, llm_stats = self.llm_handler.call_with_thinking(prompt)
        
        if not raw_output:
            return {}, llm_stats
        
        return self._parse_json_from_text(raw_output), llm_stats
    
    def _parse_json_from_text(self, text: str) -> dict:
        """從文字中解析 JSON"""
        # 清理 code fence
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 嘗試提取 JSON
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    pass
            
            logger.warning("無法解析 JSON")
            return {}
    
    def _create_success_result(
        self,
        receipt_type: ReceiptType,
        data: dict,
        confidence: float,
        issues: list,
        ocr_raw: list = None,
        ocr_stats: dict = None,
        llm_stats: list = None,
        was_corrected: bool = False,
        correction_failed: bool = False,
        gemma_correction: dict = None
    ) -> dict:
        """
        建立成功結果（符合 json_schema.md 規範）
        
        返回格式：
        {
            "ocr_result": {"text": "...", "type": "電子發票|免用統一發票收據|其他收據"},
            "ocr_stats": {"engine": "rapidocr", "total_time_s": X, ...},
            "llm_result": {receipt_type, header, items, summary, audit, ...},
            "llm_stats": [{"processor": "VLM|LLM|QR", ...}, ...],
            "invoice_type": "..."
        }
        """
        # 收據類型中文對照
        RECEIPT_TYPE_CHINESE = {
            ReceiptType.ELECTRONIC: "電子發票",
            ReceiptType.HANDWRITTEN: "免用統一發票收據",
            ReceiptType.OTHER: "其他收據",
            ReceiptType.UNKNOWN: "其他收據"
        }
        receipt_type_chinese = RECEIPT_TYPE_CHINESE.get(receipt_type, "其他收據")
        import time as time_module
        
        # 確保 data 有必要欄位（使用中文 receipt_type）
        llm_result = {
            "receipt_type": receipt_type_chinese,
            "header": data.get("header", {}),
            "items": data.get("items", []),
            "summary": data.get("summary", {}),
            "verification": data.get("verification", {}),
            "audit": {
                "confidence": round(confidence, 2),
                "issues": issues,
                "corrections": []
            }
        }
        
        # 如果有 qr_decode 資料
        if data.get("qr_decode"):
            llm_result["qr_decode"] = data["qr_decode"]
        
        # 如果有 gemma 修正記錄
        if gemma_correction:
            llm_result["audit"]["corrections"].append(gemma_correction)
        elif was_corrected:
            # 舊邏輯兼容
            llm_result["audit"]["corrections"].append({
                "source": "py_validator",
                "timestamp": int(time_module.time()),
                "description": "Python 驗算器修正"
            })
        
        # 建立 OCR result（符合 json_schema.md：只保留 text 和 type）
        ocr_result = {
            "text": self.ocr_handler.to_plain_text(ocr_raw) if ocr_raw else "",
            "type": receipt_type_chinese
        }
        
        return {
            # Worker 儲存用
            "success": True,
            "invoice_type": receipt_type.value,
            
            # OCR 結果與統計（給 complete_ocr 用）
            "ocr_result": ocr_result,
            "ocr_stats": ocr_stats,
            
            # LLM 結果與統計（給 complete_llm 用）
            "llm_result": llm_result,
            "llm_stats": llm_stats or [],
            
            # 內部使用
            "confidence": round(confidence, 2),
            "issues": issues,
            "was_corrected": was_corrected,
            "correction_failed": correction_failed
        }
    
    def _generate_markdown_from_data(self, data: dict) -> str:
        """從結構化數據生成 Markdown"""
        lines = []
        
        header = data.get("header", {})
        if header.get("supplier"):
            lines.append(f"# {header['supplier']}\n")
        
        if header.get("invoice_id"):
            lines.append(f"**發票號碼**: {header['invoice_id']}")
        if header.get("date"):
            lines.append(f"**日期**: {header['date']}")
        if header.get("tax_id"):
            lines.append(f"**統一編號**: {header['tax_id']}")
        
        lines.append("")  # 空行
        
        items = data.get("items", [])
        if items:
            lines.append("| 品名 | 數量 | 單價 | 小計 |")
            lines.append("|------|------|------|------|")
            for item in items:
                name = item.get("name", item.get("description", ""))
                qty = item.get("qty", item.get("quantity", 1))
                price = item.get("price", 0)
                total = item.get("total", 0)
                lines.append(f"| {name} | {qty} | {price} | {total} |")
            lines.append("")
        
        summary = data.get("summary", {})
        if summary.get("total"):
            lines.append(f"**合計**: {summary['total']}")
        
        return "\n".join(lines)
    
    def _create_error_result(self, receipt_type: ReceiptType, error: str, ocr_raw: list = None, ocr_stats: dict = None) -> dict:
        """建立錯誤結果（也要返回 OCR 資料，符合 json_schema.md 規範）"""
        # 收據類型中文對照
        RECEIPT_TYPE_CHINESE = {
            ReceiptType.ELECTRONIC: "電子發票",
            ReceiptType.HANDWRITTEN: "免用統一發票收據",
            ReceiptType.OTHER: "其他收據",
            ReceiptType.UNKNOWN: "其他收據"
        }
        receipt_type_chinese = RECEIPT_TYPE_CHINESE.get(receipt_type, "其他收據")
        
        # OCR result 只保留 text 和 type
        ocr_result = {
            "text": self.ocr_handler.to_plain_text(ocr_raw) if ocr_raw else "",
            "type": receipt_type_chinese
        }
        
        return {
            "success": False,
            "invoice_type": receipt_type_chinese,
            "data": {},
            "confidence": 0.0,
            "issues": [error],
            "error": error,
            "ocr_result": ocr_result,
            "ocr_stats": ocr_stats,
            "llm_result": {},
            "llm_stats": []
        }


# 向後兼容的別名
ReceiptProcessor = ReceiptProcessorV2


# 測試用
if __name__ == "__main__":
    import sys
    from backend import utils
    
    if len(sys.argv) < 2:
        print("Usage: python receipt_processor.py <image_path>")
        sys.exit(1)
    
    # 載入配置
    config = utils.load_config()
    
    # 讀取圖片
    image = utils.cv_imread_chinese(sys.argv[1])
    
    # 處理
    processor = ReceiptProcessorV2(config)
    result = processor.process(image)
    
    print("\n處理結果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
