# utils/utils.py
import cv2
import numpy as np
import os


def cv_imread_chinese(filepath: str) -> np.ndarray:
    """支援中文路徑的 OpenCV 圖像讀取。"""
    try:
        cv_img = cv2.imdecode(np.fromfile(filepath, dtype=np.uint8), -1)
        if cv_img is None:
            raise ValueError("cv2.imdecode returned None")
        return cv_img
    except Exception as e:
        raise IOError(f"讀取圖片失敗: {filepath}. 錯誤: {e}")


def cv_imwrite_chinese(filepath: str, image: np.ndarray) -> bool:
    """支援中文路徑的 OpenCV 圖像寫入。"""
    try:
        is_success, im_buf_arr = cv2.imencode(os.path.splitext(filepath)[1], image)
        if is_success:
            im_buf_arr.tofile(filepath)
            return True
        return False
    except Exception as e:
        print(f"寫入圖片失敗: {filepath}. 錯誤: {e}")
        return False
