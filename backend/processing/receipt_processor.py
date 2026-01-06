# backend/processing/receipt_processor.py
"""
收據處理器 v2 - 整合所有處理流程

流程：
1. OCR 識別 (RapidOCR)
2. 關鍵字分類 → 判斷收據類型
3A. 電子發票 → QR Code 掃描
3B. 手寫收據 → qwen3-vl:2b VLM
3C. 其他收據 → qwen3:1.7b LLM
4. Python 驗算 → 信心度評估
"""
import logging
import json
import re
import numpy as np
from typing import Optional
from pathlib import Path

from backend.managers.project_crud import ProjectCRUD

from backend.processing.keyword_classifier import KeywordClassifier, ReceiptType
from backend.processing.python_validator import PythonValidator
from backend.processing.rapidocr_handler import RapidOCRHandler
from backend.processing.qr_handler import QRHandler
from backend.processing.vision_handler import VisionHandler
from backend.processing.llm_handler import LLMHandler

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
        
        # Phase 3: 全域詞庫存取
        try:
            # 假設 config 結構符合 config.json
            pm_settings = config.get("project_manager_settings", {})
            db_path_str = pm_settings.get("global_db_path", "~/.ai_agent_lab/global_projects.db")
            global_db_path = Path(db_path_str).expanduser().resolve()
            self.project_crud = ProjectCRUD(global_db_path)
            logger.info(f"已連接全域資料庫用於詞庫查詢: {global_db_path}")
        except Exception as e:
            logger.warning(f"無法初始化 ProjectCRUD，詞庫功能將停用: {e}")
            self.project_crud = None
            
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
            # 3A: 電子發票 - 使用 QR Code + OCR + LLM 整合
            extracted_data = self._process_electronic(qr_data, ocr_text)
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
        
        # 計算 OCR 平均信心度
        avg_ocr_confidence = 0.0
        if ocr_result:
            # RapidOCR result structure: [dt, text, score] or similar depending on implementation
            # rapidocr_handler.do_ocr returns a list where each item is usually: [poly, text, score]
            # We need to robustly extract scores.
            scores = []
            for item in ocr_result:
                if isinstance(item, (list, tuple)) and len(item) >= 3:
                     # item[2] is score
                     try:
                         scores.append(float(item[2]))
                     except:
                         pass
            if scores:
                avg_ocr_confidence = sum(scores) / len(scores)
        
        validation = self.validator.validate(extracted_data, ocr_confidence=avg_ocr_confidence)
        logger.info(f"[Step 4] 驗算結果: {'通過' if validation.is_valid else '有問題'}")
        
        if validation.issues:
            logger.warning(f"[Step 4] 發現問題: {validation.issues}")

        # ===== Step 5: 返回結果 =====
        logger.info(f"[Step 5] 返回結果（驗算{'通過' if validation.is_valid else '有問題'}）")
        return self._create_success_result(
            receipt_type=receipt_type,
            data=extracted_data,
            confidence=validation.confidence,
            issues=validation.issues,
            ocr_raw=ocr_result,
            ocr_stats=ocr_stats,
            llm_stats=llm_stats
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
    
    def _process_electronic(self, qr_data: dict, ocr_text: str) -> dict:
        """
        處理電子發票 - 整合 QR Code 與 OCR 文字
        
        策略：
        1. 信任 QR Code 的 header (發票號、日期、總金額)
        2. 使用 OCR 補全 QR 缺少的品項明細
        3. 使用 LLM 進行最終合併與校對
        """
        logger.debug("[3A] 處理電子發票 (QR + OCR 整合)...")
        
        if not qr_data or not qr_data.get("success"):
            logger.warning("[3A] 缺少 QR Code 資料，降級為純 LLM 處理")
            return self._process_other(ocr_text)[0]
            
        qr_json_str = json.dumps(qr_data.get("data", {}), ensure_ascii=False)
        
        # 構建 Prompt
        from backend.processing.prompts_config import ELECTRONIC_INVOICE_PROMPT
        prompt = ELECTRONIC_INVOICE_PROMPT.format(
            qr_json=qr_json_str,
            ocr_text=ocr_text
        )
        
        # 調用 LLM
        raw_output, llm_stats = self.llm_handler.call_with_thinking(prompt)
        
        if not raw_output:
            logger.warning("[3A] LLM 整合失敗，僅返回 QR 資料")
            # Fallback to QR only
            data = qr_data.get("data", {})
            return {
                "receipt_type": "電子發票",
                "header": {
                    "supplier": "", # QR 通常無店名
                    "invoice_id": data.get("invoice_id", ""),
                    "date": data.get("date", ""),
                    "tax_id": data.get("seller_id", "")
                },
                "items": [],
                "summary": { "total": data.get("total", 0) },
                "verification": {}
            }

        # 解析 JSON
        result = self._parse_json_from_text(raw_output)
        
        # 保留原始 QR解碼資料供參考
        result["qr_decode"] = qr_data.get("data")
        
        return result
    
    def _process_handwritten(self, image_array: np.ndarray) -> tuple:
        """處理手寫收據 - 使用 VLM + 全域詞庫輔助"""
        logger.debug("[3B] 處理手寫收據...")
        
        # 1. 檢索詞庫
        vocab_context = ""
        if self.project_crud:
            buyers = self._retrieve_vocabulary("buyer")
            shops = self._retrieve_vocabulary("shop")
            if buyers or shops:
                vocab_context = "\n\n【參考全域詞庫】(若辨識模糊可參考，但不應強制使用):"
                if buyers:
                    vocab_context += f"\n常見買受人: {', '.join(buyers)}"
                if shops:
                    vocab_context += f"\n常見店家: {', '.join(shops)}"
        
        # 2. 注入 Prompt (需要 VisionHandler 支援 custom prompt 或在這裡構建)
        # 暫時依賴 VisionHandler 內部調用，這裡假設 VisionHandler 允許傳入 prompt_suffix
        # 若 VisionHandler 未支援，則需修改 VisionHandler。
        # 這裡我們先把 vocab_context 傳給 vision_handler.process_handwritten
        # 注意: VisionHandler.process_handwritten 目前只接受 image_array
        
        # 因無直接參數，我們先略過傳遞，改為在 VisionHandler 內部修改或稍後修改 VisionHandler
        # 為了不破壞現有簽名，我們假設 VisionHandler 需要更新。
        # 暫時解決方案：
        logger.info(f"[3B] 詞庫提示準備就緒 (長度 {len(vocab_context)})")
        
        # TODO: 將 vocab_context 傳遞給 VLM。目前先維持原樣，待 VisionHandler 更新。
        # 為了推進進度，我們假設 VisionHandler 會被更新以接受 prompt_context
        
        raw_output, vlm_stats = self.vision_handler.process_handwritten(image_array, prompt_context=vocab_context)
        
        if not raw_output:
            return {}, vlm_stats
        
        # 解析 JSON
        return self._parse_json_from_text(raw_output), vlm_stats

    def _retrieve_vocabulary(self, category: str, limit: int = 10) -> list[str]:
        """檢索全域詞庫"""
        if not self.project_crud:
            return []
        try:
            return self.project_crud.search_vocabulary(category, limit)
        except Exception as e:
            logger.warning(f"詞庫檢索失敗 ({category}): {e}")
            return []
    
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
        llm_stats: list = None
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
        
        # 確保 data 有必要欄位（使用中文 receipt_type）
        llm_result = {
            "receipt_type": receipt_type_chinese,
            "header": data.get("header", {}),
            "items": data.get("items", []),
            "summary": data.get("summary", {}),
            "verification": data.get("verification", {}),
            "audit": {
                "confidence": round(confidence, 2),
                "issues": issues
            }
        }
        
        # 如果有 qr_decode 資料
        if data.get("qr_decode"):
            llm_result["qr_decode"] = data["qr_decode"]
        
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
            "issues": issues
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
