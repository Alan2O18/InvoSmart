# backend/processing/python_validator.py
"""
Python 驗算器 - 使用純 Python 邏輯驗算收據數據

驗算項目：
1. items 各項 qty * price = total
2. items 總和 = summary.total
3. 必填欄位檢查
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """驗算結果"""
    is_valid: bool
    confidence: float
    issues: list[str]
    calculated_total: float
    reported_total: float


class PythonValidator:
    """
    收據驗算器
    
    使用純 Python 邏輯驗算收據數據，
    不依賴 LLM，速度快且結果確定。
    """
    
    def __init__(self, config: dict = None):
        """初始化驗算器"""
        self.config = config or {}
        self.tolerance = self.config.get("tolerance", 1)  # 誤差容忍值
        logger.info("PythonValidator 初始化完成")
    
    def validate(self, data: dict) -> ValidationResult:
        """
        驗算收據數據
        
        Args:
            data: 收據 JSON 數據
            
        Returns:
            ValidationResult: 驗算結果
        """
        issues = []
        
        # 取得 items 和 summary
        items = data.get("items", [])
        summary = data.get("summary", {})
        reported_total = self._to_number(summary.get("total", 0))
        
        # 1. 驗算各項小計
        item_issues = self._validate_items(items)
        issues.extend(item_issues)
        
        # 2. 驗算總額
        calculated_total = sum(self._to_number(item.get("total", 0)) for item in items)
        
        if abs(calculated_total - reported_total) > self.tolerance:
            issues.append(
                f"總額不符: 計算={calculated_total}, 申報={reported_total}, "
                f"差異={abs(calculated_total - reported_total)}"
            )
        
        # 3. 必填欄位檢查
        field_issues = self._validate_required_fields(data)
        issues.extend(field_issues)
        
        # 計算信心度
        is_valid = len(issues) == 0
        if is_valid:
            confidence = 0.95
        else:
            # 根據問題數量降低信心度
            confidence = max(0.3, 0.9 - len(issues) * 0.15)
        
        result = ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            issues=issues,
            calculated_total=calculated_total,
            reported_total=reported_total
        )
        
        if issues:
            logger.warning(f"驗算發現 {len(issues)} 個問題: {issues}")
        else:
            logger.info("驗算通過，無問題")
        
        return result
    
    def _validate_items(self, items: list) -> list[str]:
        """驗算各項小計"""
        issues = []
        
        for i, item in enumerate(items):
            name = item.get("name", f"品項{i+1}")
            qty = self._to_number(item.get("qty", 1))
            price = self._to_number(item.get("price", 0))
            total = self._to_number(item.get("total", 0))
            
            expected = qty * price
            
            if abs(expected - total) > self.tolerance:
                issues.append(
                    f"品項 '{name}' 計算錯誤: {qty} × {price} = {expected}, "
                    f"實際填寫 {total}"
                )
        
        return issues
    
    def _validate_required_fields(self, data: dict) -> list[str]:
        """檢查必填欄位"""
        issues = []
        header = data.get("header", {})
        
        # 日期是必填
        if not header.get("date"):
            issues.append("缺少日期")
        
        # 商家名稱或發票號碼至少要有一個
        if not header.get("supplier") and not header.get("invoice_id"):
            issues.append("缺少商家名稱和發票號碼")
        
        # 至少要有一個品項
        if not data.get("items"):
            issues.append("缺少品項")
        
        return issues
    
    def _to_number(self, value) -> float:
        """安全轉換為數字"""
        if value is None:
            return 0
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # 移除逗號和空格
            cleaned = value.replace(",", "").replace(" ", "").strip()
            try:
                return float(cleaned)
            except ValueError:
                # 嘗試解析中文數字
                return self._parse_chinese_number(cleaned)
        
        return 0
    
    def _parse_chinese_number(self, text: str) -> float:
        """嘗試解析中文數字"""
        mapping = {
            "零": 0, "壹": 1, "貳": 2, "參": 3, "肆": 4,
            "伍": 5, "陸": 6, "柒": 7, "捌": 8, "玖": 9,
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9,
        }
        
        units = {
            "拾": 10, "佰": 100, "仟": 1000, "萬": 10000,
            "十": 10, "百": 100, "千": 1000,
        }
        
        total = 0
        current = 0
        
        for char in text:
            if char in mapping:
                current = mapping[char]
            elif char in units:
                if current == 0:
                    current = 1  # 處理「拾」= 10 的情況
                total += current * units[char]
                current = 0
            elif char in ["元", "整", "角", "分"]:
                continue
            else:
                # 遇到無法解析的字符，放棄
                return 0
        
        total += current  # 加上最後剩餘的數字
        return float(total)


# 測試用
if __name__ == "__main__":
    validator = PythonValidator()
    
    # 測試正確數據
    test_correct = {
        "header": {"supplier": "測試商店", "date": "2024-01-15"},
        "items": [
            {"name": "商品A", "qty": 2, "price": 100, "total": 200},
            {"name": "商品B", "qty": 1, "price": 50, "total": 50}
        ],
        "summary": {"total": 250}
    }
    result1 = validator.validate(test_correct)
    print(f"正確數據測試: {result1}")
    
    # 測試錯誤數據
    test_wrong = {
        "header": {"supplier": "測試商店", "date": "2024-01-15"},
        "items": [
            {"name": "商品A", "qty": 2, "price": 100, "total": 180},  # 錯誤
            {"name": "商品B", "qty": 1, "price": 50, "total": 50}
        ],
        "summary": {"total": 300}  # 也錯
    }
    result2 = validator.validate(test_wrong)
    print(f"錯誤數據測試: {result2}")
