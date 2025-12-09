# processing/ocr_handler.py
import logging
import numpy as np
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)


class OCRHandler:
    def __init__(self, config: dict):
        logger.debug("正在初始化 PaddleOCR 引擎...")
        self.config = config
        try:
            self.engine = PaddleOCR(
                use_textline_orientation=config["ocr_settings"].get(
                    "use_angle_cls", True
                ),
                lang=config["ocr_settings"].get("language", "chinese_cht"),
            )
            logger.debug("PaddleOCR 引擎初始化完畢")
        except Exception as e:
            logger.error(f"初始化 PaddleOCR 失敗: {e}", exc_info=True)
            raise RuntimeError(f"初始化 PaddleOCR 失敗: {e}")

    def do_paddleocr(self, image_array: np.ndarray) -> list[dict]:
        """
        使用 PaddleOCR 辨识文字，并返回一个包含文字和坐标的字典列表。
        每个字典的格式为: {'text': '识别的文字', 'box': [x_min, y_min, x_max, y_max]}
        """
        logger.debug("執行 PaddleOCR 辨識...")
        result_dict = self.engine.predict(image_array)
        result_dict = result_dict[0]

        structured_results = []
        if result_dict and "dt_polys" in result_dict and "rec_texts" in result_dict:
            detection_polygons = result_dict["dt_polys"]
            recognized_texts = result_dict["rec_texts"]

            # 将多边形坐标 (4个点) 转换为简单的边界框 (左上角, 右下角)
            for poly, text in zip(detection_polygons, recognized_texts):
                # poly 是一个 numpy 数组，形状为 (4, 2)
                # 计算 x_min, y_min, x_max, y_max
                x_min = int(min(p[0] for p in poly))
                y_min = int(min(p[1] for p in poly))
                x_max = int(max(p[0] for p in poly))
                y_max = int(max(p[1] for p in poly))

                structured_results.append(
                    {"text": text, "box": [x_min, y_min, x_max, y_max]}
                )

        logger.debug(f"OCR 辨識完成，共 {len(structured_results)} 個文字區塊")
        return structured_results

    def reconstruct_layout(self, structured_ocr_data: list[dict]) -> str:
        if not structured_ocr_data:
            return ""
        data = sorted(structured_ocr_data, key=lambda item: item["box"][1])
        heights = [item["box"][3] - item["box"][1] for item in data]
        median_height = sorted(heights)[len(heights) // 2] if heights else 10
        y_threshold = median_height * 0.5
        lines, current_line = [], []
        if not data:
            return ""
        current_line.append(data[0])
        for i in range(1, len(data)):
            prev_box_y = current_line[0]["box"][1]
            current_box_y = data[i]["box"][1]
            if abs(current_box_y - prev_box_y) <= y_threshold:
                current_line.append(data[i])
            else:
                current_line.sort(key=lambda item: item["box"][0])
                lines.append(" ".join([item["text"] for item in current_line]))
                current_line = [data[i]]
        if current_line:
            current_line.sort(key=lambda item: item["box"][0])
            lines.append(" ".join([item["text"] for item in current_line]))
        return "\n".join(lines)


if __name__ == "__main__":
    import cv2
    import numpy as np

    def cv_imread_chinese(filepath: str) -> np.ndarray:
        """支援中文路徑的 OpenCV 圖像讀取。"""
        try:
            cv_img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), -1)
            if cv_img is None:
                raise ValueError("cv2.imdecode returned None")
            return cv_img
        except Exception as e:
            raise IOError(f"讀取圖片失敗: {filepath}. 錯誤: {e}")

    t = OCRHandler({"ocr_settings": {"language": "chinese_cht", "use_angle_cls": True}})
    print(
        t.do_paddleocr(
            cv_imread_chinese(
                "C:/Users/tange/OneDrive/Desktop/all project/py for NKNU GA/done/測試3/temp_split_images/20251029_spilt_1.png"
            )
        )
    )
