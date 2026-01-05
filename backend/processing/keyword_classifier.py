# backend/processing/keyword_classifier.py
"""
關鍵字分類器 - 根據 OCR 結果判斷收據類型

透過分析 OCR 文字中的關鍵字來決定使用哪個處理路徑：
- 電子發票 → QR Code 解析
- 手寫收據 → qwen3-vl:2b VLM
- 其他收據 → qwen3:1.7b LLM
"""
import logging
import re
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ReceiptType(Enum):
    """收據類型枚舉"""
    ELECTRONIC = "electronic"    # 電子發票
    HANDWRITTEN = "handwritten"  # 手寫收據
    OTHER = "other"              # 其他收據（傳統發票、計程車證明等）
    UNKNOWN = "unknown"          # 無法判斷


@dataclass
class ClassificationResult:
    """分類結果"""
    receipt_type: ReceiptType
    confidence: float
    matched_keywords: list[str]
    reason: str


class KeywordClassifier:
    """
    關鍵字分類器
    
    使用規則匹配來判斷收據類型，優先級：
    1. 電子發票（有 QR Code 特徵）
    2. 手寫收據（免用統一發票、手寫特徵）
    3. 其他收據（傳統發票、計程車等）
    """
    
    # 電子發票關鍵字
    ELECTRONIC_KEYWORDS = [
        "電子發票",
        "載具",
        "愛心碼",
        "手機條碼",
        "會員載具",
    ]
    
    # 電子發票特徵模式
    ELECTRONIC_PATTERNS = [
        r"\*\*",                           # QR Code 分隔符
        r"[A-Z]{2}[-]?\d{8}",              # 發票號碼格式 AB-12345678
    ]
    
    # 手寫收據關鍵字
    HANDWRITTEN_KEYWORDS = [
        "免用統一發票",
        "收據",
        "壹", "貳", "參", "肆", "伍", "陸", "柒", "捌", "玖", "拾",  # 大寫中文數字
        "萬", "仟", "佰", "拾",            # 金額單位
        "元整",
    ]
    
    # 其他收據關鍵字
    OTHER_KEYWORDS = [
        "統一發票",
        "統一編號",
        "營業人",
        "乘車證明",
        "計程車",
        "車資",
        "里程",
        "發票",
    ]
    
    def __init__(self, config: dict = None):
        """初始化分類器"""
        self.config = config or {}
        logger.info("KeywordClassifier 初始化完成")
    
    def classify(self, ocr_text: str, has_qr_code: bool = False) -> ClassificationResult:
        """
        根據 OCR 文字分類收據類型
        
        Args:
            ocr_text: OCR 識別的文字
            has_qr_code: 是否偵測到 QR Code（由 QR 掃描器提供）
            
        Returns:
            ClassificationResult: 分類結果
        """
        if not ocr_text:
            return ClassificationResult(
                receipt_type=ReceiptType.UNKNOWN,
                confidence=0.0,
                matched_keywords=[],
                reason="OCR 文字為空"
            )
        
        text_upper = ocr_text.upper()
        
        # 1. 優先檢查電子發票
        electronic_matches = self._match_electronic(ocr_text, text_upper, has_qr_code)
        if electronic_matches["score"] >= 2 or has_qr_code:
            return ClassificationResult(
                receipt_type=ReceiptType.ELECTRONIC,
                confidence=min(0.95, 0.5 + electronic_matches["score"] * 0.15),
                matched_keywords=electronic_matches["keywords"],
                reason="偵測到電子發票特徵"
            )
        
        # 2. 檢查手寫收據
        handwritten_matches = self._match_handwritten(ocr_text)
        if handwritten_matches["score"] >= 2:
            return ClassificationResult(
                receipt_type=ReceiptType.HANDWRITTEN,
                confidence=min(0.9, 0.5 + handwritten_matches["score"] * 0.1),
                matched_keywords=handwritten_matches["keywords"],
                reason="偵測到手寫收據特徵"
            )
        
        # 3. 檢查其他收據
        other_matches = self._match_other(ocr_text)
        if other_matches["score"] >= 1:
            return ClassificationResult(
                receipt_type=ReceiptType.OTHER,
                confidence=min(0.85, 0.5 + other_matches["score"] * 0.1),
                matched_keywords=other_matches["keywords"],
                reason="偵測到傳統收據/發票特徵"
            )
        
        # 4. 無法判斷，預設為其他收據
        return ClassificationResult(
            receipt_type=ReceiptType.OTHER,
            confidence=0.5,
            matched_keywords=[],
            reason="無法判斷類型，使用預設處理流程"
        )
    
    def _match_electronic(self, text: str, text_upper: str, has_qr: bool) -> dict:
        """匹配電子發票特徵"""
        keywords = []
        score = 0
        
        # QR Code 是強特徵
        if has_qr:
            score += 3
            keywords.append("QR Code")
        
        # 關鍵字匹配
        for kw in self.ELECTRONIC_KEYWORDS:
            if kw in text:
                score += 1
                keywords.append(kw)
        
        # 模式匹配
        for pattern in self.ELECTRONIC_PATTERNS:
            if re.search(pattern, text):
                score += 1
                keywords.append(f"pattern:{pattern}")
        
        return {"score": score, "keywords": keywords}
    
    def _match_handwritten(self, text: str) -> dict:
        """匹配手寫收據特徵"""
        keywords = []
        score = 0
        
        for kw in self.HANDWRITTEN_KEYWORDS:
            if kw in text:
                score += 1
                keywords.append(kw)
                
                # 大寫中文數字是強特徵
                if kw in ["壹", "貳", "參", "肆", "伍", "陸", "柒", "捌", "玖"]:
                    score += 1
        
        # 「免用統一發票」是強特徵
        if "免用統一發票" in text:
            score += 2
        
        return {"score": score, "keywords": keywords}
    
    def _match_other(self, text: str) -> dict:
        """匹配其他收據特徵"""
        keywords = []
        score = 0
        
        for kw in self.OTHER_KEYWORDS:
            if kw in text:
                score += 1
                keywords.append(kw)
        
        return {"score": score, "keywords": keywords}


# 測試用
if __name__ == "__main__":
    classifier = KeywordClassifier()
    
    # 測試電子發票
    test1 = "電子發票 AB-12345678 **"
    result1 = classifier.classify(test1)
    print(f"電子發票測試: {result1}")
    
    # 測試手寫收據
    test2 = "免用統一發票收據 壹仟貳佰元整"
    result2 = classifier.classify(test2)
    print(f"手寫收據測試: {result2}")
    
    # 測試計程車
    test3 = "計程車乘車證明 車資 里程"
    result3 = classifier.classify(test3)
    print(f"計程車測試: {result3}")
