# utils/utils.py
import cv2
import numpy as np
import os
import logging
from pathlib import Path
import shutil
import tempfile
from typing import List, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import UploadFile

logger = logging.getLogger(__name__)


def cv_imread_chinese(filepath: str) -> np.ndarray:
    """支援中文路徑的 OpenCV 圖像讀取，並擴充 JXL 支援。"""
    try:
        source = Path(filepath)

        # 針對 JXL 案件進行特別處理 (因為 cv2.imdecode 不支援 JXL)
        if source.suffix.lower() == ".jxl":
            import imagecodecs

            raw = source.read_bytes()
            # imagecodecs 回傳通常是 RGB，轉換為 BGR 以符合 OpenCV 慣例
            arr = imagecodecs.jpegxl_decode(raw)
            if len(arr.shape) == 3 and arr.shape[2] == 3:
                return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            return arr

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
        logger.error(f"寫入圖片失敗: {filepath}. 錯誤: {e}")
        return False

@asynccontextmanager
async def handle_upload_files(files: List[UploadFile]) -> AsyncGenerator[List[str], None]:
    """
    非同步 Context Manager，處理上傳檔案並自動清理暫存資料夾。
    
    Args:
        files: FastAPI UploadFile 列表
        
    Yields:
        List[str]: 已儲存到暫存目錄的檔案絕對路徑列表
    """
    temp_dir = tempfile.mkdtemp()
    saved_file_paths = []
    
    try:
        for file in files:
            file_path = os.path.join(temp_dir, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            saved_file_paths.append(file_path)
            
        yield saved_file_paths
        
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

