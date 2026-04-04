# backend/processing/qr_handler.py
"""
QR Code Handler - 台灣電子發票 QR Code 解碼器 (使用 QReader)

使用 QReader (YOLOv8 + pyzbar) 增強對模糊、傾斜、低對比度 QR Code 的辨識能力。

電子發票 QR Code 格式說明：
- 左側 QR Code：包含發票號碼、日期、賣方統編、總金額等
- 右側 QR Code：包含品項明細（加密）

本模組主要解碼左側 QR Code 取得關鍵資料。
"""
import logging
import numpy as np
import cv2
from typing import Optional

try:
    from qreader import QReader
    QREADER_AVAILABLE = True
except ImportError:
    QREADER_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("QReader 未安裝，請執行 `pip install qreader`")

logger = logging.getLogger(__name__)


class QRHandler:
    """
    台灣電子發票 QR Code 解碼器
    
    使用 QReader 進行增強型偵測與解碼。
    """

    def __init__(self, config: dict):
        """
        初始化 QR Handler
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.qreader = None
        
        if QREADER_AVAILABLE:
            try:
                # 初始化 QReader (model_size='n' for speed/nano, or 's' for small)
                # 使用 'n' (nano) 以求速度與準確度的平衡，若需要更高準確度可改為 's'
                logger.info("正在初始化 QReader (YOLOv8)...")
                self.qreader = QReader(model_size='n')
                logger.info("QReader 初始化完成")
            except Exception as e:
                logger.error(f"QReader 初始化失敗: {e}")
        else:
            logger.warning("QRHandler: QReader 模組不可用")

    def detect_and_decode(self, image_array: np.ndarray) -> Optional[dict]:
        """
        偵測並解碼電子發票 QR Code (左側 QR)
        
        Args:
            image_array: OpenCV 格式的圖片陣列 (BGR)
        
        Returns:
            dict: 解碼成功時返回發票資料
                {
                    "invoice_id": "AB12345678",
                    "date": "2024-01-15",
                    "seller_id": "12345678",
                    "total": 150,
                    "buyer_id": "",
                    "random_code": "1234",
                    "raw_data": "原始 QR 字串"
                }
            None: 未偵測到 QR Code 或解碼失敗
        """
        if not self.qreader:
            return None

        try:
            # QReader 預期 RGB 格式
            if len(image_array.shape) == 3:
                image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)

            # 偵測並解碼 (return_detections=False 預設只返回解碼文字列表)
            decoded_texts = self.qreader.detect_and_decode(image=image_rgb)
            
            if not decoded_texts:
                logger.debug("未偵測到此圖片的 QR Code")
                return None

            # 遍歷解碼結果，尋找符合電子發票格式的
            for text in decoded_texts:
                if not text:
                    continue
                    
                parsed = self._parse_taiwan_einvoice_qr(text)
                if parsed:
                    logger.info(f"成功解碼電子發票 QR Code: {parsed.get('invoice_id', 'N/A')}")
                    return parsed

            logger.debug(f"偵測到 {len(decoded_texts)} 個 QR Code，但無有效電子發票格式")
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
            # logger.debug(f"解析電子發票 QR 格式失敗(非目標格式): {e}")
            return None

    def is_electronic_invoice(self, image_array: np.ndarray) -> bool:
        """
        快速檢查圖片是否為電子發票
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
            注意：QReader detection 返回的是 (x1, y1, x2, y2)
        """
        if not self.qreader:
            return []

        try:
             # QReader 預期 RGB
            if len(image_array.shape) == 3:
                image_rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            else:
                image_rgb = cv2.cvtColor(image_array, cv2.COLOR_GRAY2RGB)

            # return_detections=True returns list of tuples (decoded_text, bbox_tuple)
            # where bbox_tuple might be None or (x1, y1, x2, y2)
            # Note: QReader API may vary; handle robustly
            detections = self.qreader.detect_and_decode(image=image_rgb, return_detections=True)
            
            locations = []
            if not detections:
                return locations
                
            for item in detections:
                try:
                    # Handle both tuple and list formats
                    if isinstance(item, (tuple, list)) and len(item) >= 2:
                        text, bbox = item[0], item[1]
                    else:
                        continue
                        
                    if bbox is not None and len(bbox) >= 4:
                        x1, y1, x2, y2 = map(int, bbox[:4])
                        w = x2 - x1
                        h = y2 - y1
                        locations.append((x1, y1, w, h))
                except (ValueError, TypeError, IndexError) as e:
                    logger.debug(f"Skipping invalid detection item: {e}")
                    continue
            
            return locations

        except Exception as e:
            logger.error(f"取得 QR 位置失敗: {e}")
            return []


# 測試用
if __name__ == "__main__":
    import sys
    from backend.utils import utils
    
    # 設定 logger
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 2:
        print("Usage: python qr_handler.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    try:
        image = utils.cv_imread_chinese(image_path)
    except Exception:
        image = None
    
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
