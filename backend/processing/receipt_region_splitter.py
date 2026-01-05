"""
Receipt Region Splitter Module
收據分區切割模組

將免用統一發票收據圖片切割成 5 個區域：
1. Buyer (左上): 買受人、地址
2. Date (右上): 日期
3. Table (左側): 品名、數量、單價、金額
4. Stamp (右側): 店章、統編
5. Summary (底部): 大寫金額合計
"""

import cv2
import os
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np


# 預設切割比例 (5區域版面 - 加大重疊區域)
# 每個區域都向外擴展一些，避免文字被切斷
DEFAULT_RATIOS = {
    'header_end': 0.28,    # Header 區擴大到 28% (原 20%)
    'main_end': 0.88,      # 主體區擴大到 88% (原 82%)
    'left_ratio': 0.70,    # 左側佔 70% (原 65%)，讓品項區更大
    # 區域重疊設定
    'overlap_v': 0.05,     # 垂直方向重疊 5%
    'overlap_h': 0.08,     # 水平方向重疊 8%
}


def load_image(image_path: str) -> Optional[np.ndarray]:
    """
    載入圖片 (支援中文路徑)
    
    Args:
        image_path: 圖片路徑
        
    Returns:
        OpenCV 圖片陣列，失敗回傳 None
    """
    if not os.path.exists(image_path):
        print(f"[ERROR] Image not found: {image_path}")
        return None
    
    # 使用 numpy 讀取以支援中文路徑
    try:
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            print(f"[ERROR] Failed to decode image: {image_path}")
            return None
        return image
    except Exception as e:
        print(f"[ERROR] Failed to load image: {image_path}, {e}")
        return None


def split_receipt_regions(
    image: np.ndarray,
    ratios: Dict[str, float] = None
) -> Dict[str, np.ndarray]:
    """
    將收據圖片切割成 5 個區域 (含左右分割 + 重疊)
    
    重疊設計：避免文字被切斷在邊界上
    
    Args:
        image: OpenCV 圖片陣列
        ratios: 自訂切割比例 (可選)
        
    Returns:
        包含 5 個區域的字典
    """
    if ratios is None:
        ratios = DEFAULT_RATIOS
    
    h, w = image.shape[:2]
    
    # 基礎切割點
    header_end = int(h * ratios['header_end'])
    main_end = int(h * ratios['main_end'])
    mid_w = int(w * ratios['left_ratio'])
    
    # 重疊量
    overlap_v = int(h * ratios.get('overlap_v', 0.05))
    overlap_h = int(w * ratios.get('overlap_h', 0.08))
    
    # 帶重疊的區域切割
    # buyer: 從頭開始，向下擴展 + 向右擴展
    buyer_bottom = min(header_end + overlap_v, h)
    buyer_right = min(mid_w + overlap_h, w)
    
    # date: 向上擴展 + 向左擴展
    date_left = max(mid_w - overlap_h, 0)
    date_bottom = min(header_end + overlap_v, h)
    
    # table: 向上擴展 + 向下擴展 + 向右擴展
    table_top = max(header_end - overlap_v, 0)
    table_bottom = min(main_end + overlap_v, h)
    table_right = min(mid_w + overlap_h, w)
    
    # stamp: 向上擴展 + 向下擴展 + 向左擴展
    stamp_top = max(header_end - overlap_v, 0)
    stamp_bottom = min(main_end + overlap_v, h)
    stamp_left = max(mid_w - overlap_h, 0)
    
    # summary: 向上擴展
    summary_top = max(main_end - overlap_v, 0)
    
    regions = {
        'buyer':   image[0:buyer_bottom, 0:buyer_right],
        'date':    image[0:date_bottom, date_left:w],
        'table':   image[table_top:table_bottom, 0:table_right],
        'stamp':   image[stamp_top:stamp_bottom, stamp_left:w],
        'summary': image[summary_top:h, :],
    }
    
    return regions


def save_regions(
    regions: Dict[str, np.ndarray],
    output_dir: str,
    base_name: str = "region"
) -> Dict[str, str]:
    """
    將切割區域儲存為檔案
    
    Args:
        regions: 區域圖片字典
        output_dir: 輸出目錄
        base_name: 檔案名稱前綴
        
    Returns:
        儲存路徑字典
    """
    os.makedirs(output_dir, exist_ok=True)
    
    saved_paths = {}
    for region_name, region_image in regions.items():
        output_path = os.path.join(output_dir, f"{base_name}_{region_name}.jpg")
        # 使用 imencode 支援中文路徑
        _, encoded = cv2.imencode('.jpg', region_image)
        encoded.tofile(output_path)
        saved_paths[region_name] = output_path
        print(f"  [Saved] {region_name}: {output_path}")
    
    return saved_paths


def split_and_save(
    image_path: str,
    output_dir: str = None
) -> Optional[Dict[str, str]]:
    """
    主函式：載入圖片、切割、儲存
    
    Args:
        image_path: 輸入圖片路徑
        output_dir: 輸出目錄 (預設為圖片同目錄下的 'regions' 資料夾)
        
    Returns:
        儲存路徑字典，失敗回傳 None
    """
    image = load_image(image_path)
    if image is None:
        return None
    
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(image_path), "regions")
    
    base_name = Path(image_path).stem
    
    print(f"[Splitting] {image_path}")
    print(f"  Image size: {image.shape[1]}x{image.shape[0]}")
    
    regions = split_receipt_regions(image)
    saved_paths = save_regions(regions, output_dir, base_name)
    
    return saved_paths


# ==========================================
# 測試用
# ==========================================
if __name__ == "__main__":
    import sys
    
    # 預設測試圖片
    test_images = [
        "docs/手寫收據20251117_split_0_1766302781.jpg",
        "docs/手寫收據20251117_split_1_1766160419.jpg",
        "docs/燕巢小宏遠4.2_split_1_1766302789.jpg",
    ]
    
    # 如果有命令列參數，使用參數指定的圖片
    if len(sys.argv) > 1:
        test_images = sys.argv[1:]
    
    print("=" * 60)
    print("Receipt Region Splitter Test (5-Region Layout)")
    print("=" * 60)
    
    for img_path in test_images:
        result = split_and_save(img_path)
        if result:
            print(f"  ✅ Success: {len(result)} regions saved")
        else:
            print(f"  ❌ Failed")
        print()
