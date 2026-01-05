# backend/processing/qr_handler.py
"""
QR Code Handler - 台灣電子發票 QR Code 解碼器

電子發票 QR Code 格式說明：
- 左側 QR Code：包含發票號碼、日期、賣方統編、總金額等
- 右側 QR Code：包含品項明細（加密）

本模組主要解碼左側 QR Code 取得關鍵資料。
"""
import logging
import numpy as np
import cv2
from typing import Optional

logger = logging.getLogger(__name__)

# 嘗試導入 pyzbar，如果失敗則標記為不可用
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    from pyzbar.pyzbar import ZBarSymbol
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
    logger.warning("pyzbar 未安裝，QR Code 解碼功能不可用")


class QRHandler:
    """
    台灣電子發票 QR Code 解碼器
    
    電子發票包含兩個 QR Code：
    - 左 QR：發票基本資訊（明文）
    - 右 QR：品項明細（加密，需解密金鑰）
    
    本處理器專注於解碼左 QR 取得可驗證的發票資訊。
    """

    def __init__(self, config: dict):
        """
        初始化 QR Handler
        
        Args:
            config: 配置字典
        """
        self.config = config
        if not PYZBAR_AVAILABLE:
            logger.warning("QRHandler 初始化：pyzbar 不可用，將無法解碼 QR Code")

    def detect_and_decode(self, image_array: np.ndarray) -> Optional[dict]:
        """
        偵測並解碼電子發票 QR Code
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
        
        Returns:
            dict: 解碼成功時返回發票資料
                {
                    "invoice_id": "AB12345678",
                    "date": "2024-01-15",
                    "seller_id": "12345678",
                    "total": 150,
                    "buyer_id": "",  # 可能為空
                    "random_code": "1234",
                    "raw_data": "原始 QR 字串"
                }
            None: 未偵測到 QR Code 或解碼失敗
        """
        if not PYZBAR_AVAILABLE:
            logger.debug("pyzbar 不可用，跳過 QR 解碼")
            return None

        try:
            # 確保圖片是灰階（pyzbar 在灰階下效果更好）
            if len(image_array.shape) == 3:
                gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
            else:
                gray = image_array

            # 嘗試解碼 QR Code
            decoded_objects = pyzbar_decode(gray, symbols=[ZBarSymbol.QRCODE])
            
            if not decoded_objects:
                logger.debug("未偵測到 QR Code")
                return None

            # 尋找符合台灣電子發票格式的 QR Code
            for obj in decoded_objects:
                try:
                    raw_data = obj.data.decode('utf-8')
                    parsed = self._parse_taiwan_einvoice_qr(raw_data)
                    if parsed:
                        logger.info(f"成功解碼電子發票 QR Code: {parsed.get('invoice_id', 'N/A')}")
                        return parsed
                except Exception as e:
                    logger.debug(f"解析 QR 資料失敗: {e}")
                    continue

            logger.debug("偵測到 QR Code 但非電子發票格式")
            return None

        except Exception as e:
            logger.error(f"QR Code 解碼失敗: {e}", exc_info=True)
            return None

    def _parse_taiwan_einvoice_qr(self, raw_data: str) -> Optional[dict]:
        """
        解析台灣電子發票 QR Code 資料
        
        左側 QR Code 格式（約 77 字元）：
        - 位置 0-9:   發票號碼 (AB12345678)
        - 位置 10-16: 發票日期 (1130115 = 民國113年01月15日)  
        - 位置 17-24: 隨機碼 (4位) + 未稅金額 (8位16進制)
        - 位置 25-32: 稅額 (8位16進制)
        - 位置 33-40: 買方統編 (8位，無則為00000000)
        - 位置 41-48: 賣方統編 (8位)
        - 位置 49+:   加密驗證碼等
        
        Args:
            raw_data: QR Code 原始字串
            
        Returns:
            dict: 解析成功的發票資料，失敗返回 None
        """
        # 基本長度檢查（至少要有 50 字元）
        if not raw_data or len(raw_data) < 50:
            return None

        try:
            # 發票號碼：2碼英文 + 8碼數字
            invoice_number = raw_data[0:10]
            if not (invoice_number[:2].isalpha() and invoice_number[2:].isdigit()):
                return None

            # 發票日期：民國年月日 (7碼)
            date_str = raw_data[10:17]
            if not date_str.isdigit():
                return None
            
            # 轉換民國年為西元年
            roc_year = int(date_str[0:3])
            month = date_str[3:5]
            day = date_str[5:7]
            western_year = roc_year + 1911
            formatted_date = f"{western_year}-{month}-{day}"

            # 隨機碼 (4碼)
            random_code = raw_data[17:21]

            # 未稅金額 (8位16進制)
            try:
                untaxed_hex = raw_data[21:29]
                untaxed_amount = int(untaxed_hex, 16)
            except ValueError:
                untaxed_amount = 0

            # 稅額 (8位16進制)  
            try:
                tax_hex = raw_data[29:37]
                tax_amount = int(tax_hex, 16)
            except ValueError:
                tax_amount = 0

            # 總金額
            total_amount = untaxed_amount + tax_amount

            # 買方統編
            buyer_tax_id = raw_data[37:45]
            if buyer_tax_id == "00000000":
                buyer_tax_id = ""

            # 賣方統編
            seller_tax_id = raw_data[45:53]

            return {
                "invoice_id": invoice_number,
                "date": formatted_date,
                "seller_id": seller_tax_id,
                "buyer_id": buyer_tax_id,
                "total": total_amount,
                "untaxed_amount": untaxed_amount,
                "tax_amount": tax_amount,
                "random_code": random_code,
                "raw_data": raw_data
            }

        except Exception as e:
            logger.debug(f"解析電子發票 QR 格式失敗: {e}")
            return None

    def is_electronic_invoice(self, image_array: np.ndarray) -> bool:
        """
        快速檢查圖片是否為電子發票（有 QR Code）
        
        Args:
            image_array: OpenCV 格式的圖片陣列
            
        Returns:
            bool: True 如果偵測到電子發票 QR Code
        """
        result = self.detect_and_decode(image_array)
        return result is not None

    def get_qr_locations(self, image_array: np.ndarray) -> list:
        """
        取得圖片中所有 QR Code 的位置
        
        Args:
            image_array: OpenCV 格式的圖片陣列
            
        Returns:
            list: QR Code 邊界框列表 [(x, y, w, h), ...]
        """
        if not PYZBAR_AVAILABLE:
            return []

        try:
            if len(image_array.shape) == 3:
                gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
            else:
                gray = image_array

            decoded_objects = pyzbar_decode(gray, symbols=[ZBarSymbol.QRCODE])
            
            locations = []
            for obj in decoded_objects:
                rect = obj.rect
                locations.append((rect.left, rect.top, rect.width, rect.height))
            
            return locations

        except Exception as e:
            logger.error(f"取得 QR 位置失敗: {e}")
            return []


# 測試用
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python qr_handler.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    image = cv2.imread(image_path)
    
    if image is None:
        print(f"無法讀取圖片: {image_path}")
        sys.exit(1)
    
    handler = QRHandler({})
    result = handler.detect_and_decode(image)
    
    if result:
        print("偵測到電子發票 QR Code:")
        for key, value in result.items():
            if key != "raw_data":
                print(f"  {key}: {value}")
    else:
        print("未偵測到電子發票 QR Code")
