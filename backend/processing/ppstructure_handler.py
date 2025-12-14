# processing/ppstructure_handler.py
"""
PP-Structure Handler - Advanced OCR processing using PaddleOCR's enhanced configuration.

This module provides enhanced OCR capabilities including:
- Advanced layout analysis and text detection
- Automatic text rotation detection and correction
- Structured output formatting to Markdown
- Simplified to Traditional Chinese conversion

Note: This implementation uses PaddleOCR with enhanced configuration instead of the
unavailable PPStructure API.
"""
import logging
import numpy as np
from paddleocr import PaddleOCR
from markdownify import markdownify as md
from opencc import OpenCC

logger = logging.getLogger(__name__)


class PPStructureHandler:
    """
    Advanced OCR handler using PaddleOCR for receipt processing.
    
    Uses enhanced PaddleOCR configuration to provide better document understanding
    compared to basic OCR, especially for structured documents like receipts.
    """

    def __init__(self, config: dict):
        """
        Initialize the enhanced PaddleOCR engine.
        
        Args:
            config: Configuration dictionary with 'ocr_settings' and 'text_processing' keys.
        """
        logger.debug("正在初始化增強型 PaddleOCR 引擎...")
        self.config = config
        
        # Get settings from config
        ocr_settings = config.get("ocr_settings", {})
        
        try:
            # Initialize PaddleOCR with minimal settings for new API (v3.2+)
            # Note: Many old parameters are no longer supported in new API
            lang = ocr_settings.get("language", "ch")
            if lang == "chinese_cht":
                lang = "ch"  # Use 'ch' for Chinese
            
            self.engine = PaddleOCR(
                use_angle_cls=ocr_settings.get("use_angle_cls", True),
                lang=lang,
            )
            logger.debug("增強型 PaddleOCR 引擎初始化完畢")
            
            # Initialize OpenCC for Simplified to Traditional conversion
            text_processing = config.get("text_processing", {})
            opencc_config = text_processing.get("opencc_config", "s2twp")
            # Remove .json suffix if present (OpenCC handles this internally)
            if opencc_config.endswith('.json'):
                opencc_config = opencc_config[:-5]
            self.converter = OpenCC(opencc_config)
            logger.debug(f"OpenCC 轉換器初始化完畢 (配置: {opencc_config})")
            
        except Exception as e:
            logger.error(f"初始化增強型 PaddleOCR 失敗: {e}", exc_info=True)
            raise RuntimeError(f"初始化增強型 PaddleOCR 失敗: {e}")

    def do_ppstructure(self, image_array: np.ndarray) -> list:
        """
        Perform enhanced OCR analysis on the image.
        
        Returns PaddleOCR results: list of [bbox, (text, confidence)]
        
        Args:
            image_array: NumPy array of the image.
            
        Returns:
            List of OCR results from PaddleOCR.
        """
        logger.debug("執行增強型 OCR 分析...")
        try:
            # Use predict method for new PaddleOCR API (v3.2+)
            result = self.engine.predict(image_array)
            # result is typically a dict with 'rec_texts', 'dt_polys' etc.
            # or a list with one element (for single image)
            if isinstance(result, list) and len(result) > 0:
                result = result[0]  # Get the actual OCR results
            logger.debug("OCR 分析完成")
            return result if result else {}
        except Exception as e:
            logger.error(f"OCR 分析失敗: {e}", exc_info=True)
            return {}

    def ppstructure_to_markdown(self, ocr_result) -> str:
        """
        Convert PaddleOCR results to clean markdown format.
        
        This method processes OCR results and reconstructs the layout:
        - Sorts text by vertical position (top to bottom)
        - Groups text on the same line
        - Preserves reading order (left to right)
        
        Args:
            ocr_result: OCR results from PaddleOCR predict().
                New format (dict): {'dt_polys': [...], 'rec_texts': [...]}
            
        Returns:
            Formatted text string representing the document.
        """
        logger.debug("將 OCR 結果格式化...")
        if not ocr_result:
            return ""
        
        # Handle new PaddleOCR format (dict with dt_polys and rec_texts)
        if isinstance(ocr_result, dict):
            dt_polys = ocr_result.get('dt_polys', [])
            rec_texts = ocr_result.get('rec_texts', [])
            
            if not dt_polys or not rec_texts:
                return ""
            
            # Build structured data from dict format
            structured_data = []
            for poly, text in zip(dt_polys, rec_texts):
                if not text:
                    continue
                # poly is numpy array of shape (4, 2)
                y_coords = [point[1] for point in poly]
                x_coords = [point[0] for point in poly]
                y_min = min(y_coords)
                y_max = max(y_coords)
                x_min = min(x_coords)
                
                structured_data.append({
                    'text': text,
                    'y_min': y_min,
                    'y_max': y_max,
                    'x_min': x_min,
                    'y_center': (y_min + y_max) / 2
                })
        else:
            # Handle old list format for backwards compatibility
            structured_data = []
            for item in ocr_result:
                if len(item) >= 2:
                    bbox = item[0]
                    text_info = item[1]
                    text = text_info[0] if isinstance(text_info, (list, tuple)) else text_info
                    
                    y_coords = [point[1] for point in bbox]
                    x_coords = [point[0] for point in bbox]
                    y_min = min(y_coords)
                    y_max = max(y_coords)
                    x_min = min(x_coords)
                    
                    structured_data.append({
                        'text': text,
                        'y_min': y_min,
                        'y_max': y_max,
                        'x_min': x_min,
                        'y_center': (y_min + y_max) / 2
                    })
        
        if not structured_data:
            return ""
        
        # Sort by vertical position
        structured_data.sort(key=lambda x: x['y_center'])
        
        # Calculate median height for line grouping
        heights = [item['y_max'] - item['y_min'] for item in structured_data]
        median_height = sorted(heights)[len(heights) // 2] if heights else 10
        y_threshold = median_height * 0.6  # Threshold for same line
        
        # Group into lines
        lines = []
        current_line = [structured_data[0]]
        
        for i in range(1, len(structured_data)):
            prev_y = current_line[0]['y_center']
            curr_y = structured_data[i]['y_center']
            
            if abs(curr_y - prev_y) <= y_threshold:
                # Same line
                current_line.append(structured_data[i])
            else:
                # New line - sort current line by x position and add
                current_line.sort(key=lambda x: x['x_min'])
                lines.append(" ".join([item['text'] for item in current_line]))
                current_line = [structured_data[i]]
        
        # Don't forget the last line
        if current_line:
            current_line.sort(key=lambda x: x['x_min'])
            lines.append(" ".join([item['text'] for item in current_line]))
        
        result_text = "\n".join(lines)
        logger.debug(f"格式化完成，共 {len(lines)} 行")
        return result_text

    def convert_to_traditional(self, text: str) -> str:
        """
        Convert Simplified Chinese to Traditional Chinese (Taiwan variant).
        
        Uses OpenCC with 's2twp.json' config which handles:
        - Character conversion (簡體 → 繁體)
        - Vocabulary/phrase conversion (Taiwan preferences)
        
        Args:
            text: Text that may contain Simplified Chinese.
            
        Returns:
            Text converted to Traditional Chinese.
        """
        if not text:
            return ""
        
        logger.debug("執行繁簡轉換...")
        try:
            # Check if conversion is enabled
            text_processing = self.config.get("text_processing", {})
            if not text_processing.get("enable_traditional_conversion", True):
                logger.debug("繁簡轉換已停用，返回原文")
                return text
            
            converted_text = self.converter.convert(text)
            logger.debug("繁簡轉換完成")
            return converted_text
            
        except Exception as e:
            logger.error(f"繁簡轉換失敗: {e}", exc_info=True)
            # Return original text if conversion fails
            return text

    def process_receipt(self, image_array: np.ndarray) -> str:
        """
        Complete pipeline to process a receipt image.
        
        This is the main entry point that combines all processing steps:
        1. PP-Structure analysis (with automatic rotation detection)
        2. Convert results to Markdown
        3. Convert to Traditional Chinese
        
        Args:
            image_array: NumPy array of the receipt image.
            
        Returns:
            Cleaned Markdown text in Traditional Chinese.
        """
        logger.info("開始處理收據圖片...")
        
        # Step 1: Run PP-Structure analysis
        ppstructure_result = self.do_ppstructure(image_array)
        
        if not ppstructure_result:
            logger.warning("PP-Structure 未返回任何結果")
            return ""
        
        # Step 2: Convert to Markdown
        markdown_text = self.ppstructure_to_markdown(ppstructure_result)
        
        if not markdown_text:
            logger.warning("Markdown 轉換結果為空")
            return ""
        
        # Step 3: Convert to Traditional Chinese
        traditional_text = self.convert_to_traditional(markdown_text)
        
        logger.info("收據處理完成")
        return traditional_text


if __name__ == "__main__":
    import cv2
    
    def cv_imread_chinese(filepath: str) -> np.ndarray:
        """支援中文路徑的 OpenCV 圖像讀取。"""
        try:
            cv_img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), -1)
            if cv_img is None:
                raise ValueError("cv2.imdecode returned None")
            return cv_img
        except Exception as e:
            raise IOError(f"讀取圖片失敗: {filepath}. 錯誤: {e}")
    
    # Test configuration
    test_config = {
        "ocr_settings": {
            "language": "ch",
            "use_angle_cls": True,
            "use_gpu": False
        },
        "ppstructure_settings": {
            "table": True,
            "ocr": True,
            "layout": True,
            "show_log": True
        },
        "text_processing": {
            "enable_traditional_conversion": True,
            "opencc_config": "s2twp"
        }
    }
    
    # Initialize handler
    handler = PPStructureHandler(test_config)
    
    # Test with an image (replace with actual path)
    test_image_path = "test_receipt.jpg"
    try:
        image = cv_imread_chinese(test_image_path)
        result = handler.process_receipt(image)
        print("=" * 50)
        print("處理結果:")
        print("=" * 50)
        print(result)
    except Exception as e:
        print(f"測試失敗: {e}")
