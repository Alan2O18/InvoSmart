# test_ppstructure.py
"""
測試 PP-Structure Handler 功能的簡單腳本
"""
import json
import sys
import os
from pathlib import Path

# 添加 backend 到 Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from processing.ppstructure_handler import PPStructureHandler
from utils.utils import cv_imread_chinese


def test_ppstructure():
    """測試 PP-Structure handler 的基本功能"""
    
    print("=" * 60)
    print("PP-Structure Handler 測試")
    print("=" * 60)
    
    # 載入配置
    try:
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)
        print("✓ 配置文件已載入")
    except Exception as e:
        print(f"✗ 載入配置失敗: {e}")
        return
    
    # 初始化 PP-Structure handler
    try:
        handler = PPStructureHandler(config)
        print("✓ PP-Structure handler 初始化成功")
    except Exception as e:
        print(f"✗ 初始化失敗: {e}")
        return
    
    # 測試圖片路徑（請根據實際路徑修改）
    test_image_path = input("\n請輸入測試收據圖片的完整路徑（或按 Enter 跳過測試）: ").strip()
    
    if not test_image_path:
        print("\n跳過圖片處理測試")
        print("\n" + "=" * 60)
        print("基本測試完成！")
        print("=" * 60)
        print("\n下一步：")
        print("1. 準備一張收據圖片")
        print("2. 重新執行此腳本並輸入圖片路徑")
        print("3. 或直接使用系統 API 進行測試")
        return
    
    # 檢查圖片是否存在
    if not os.path.exists(test_image_path):
        print(f"✗ 圖片不存在: {test_image_path}")
        return
    
    # 讀取並處理圖片
    try:
        print(f"\n讀取圖片: {os.path.basename(test_image_path)}")
        image = cv_imread_chinese(test_image_path)
        print(f"✓ 圖片讀取成功，尺寸: {image.shape}")
    except Exception as e:
        print(f"✗ 讀取圖片失敗: {e}")
        return
    
    # 執行 PP-Structure 處理
    try:
        print("\n開始 PP-Structure 處理...")
        result = handler.process_receipt(image)
        print("✓ PP-Structure 處理完成")
        
        # 顯示結果
        print("\n" + "-" * 60)
        print("處理結果（Markdown 格式，已轉換為繁體中文）:")
        print("-" * 60)
        print(result)
        print("-" * 60)
        
        # 保存結果到文件
        output_file = "ppstructure_test_output.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"\n✓ 結果已保存至: {output_file}")
        
    except Exception as e:
        print(f"✗ PP-Structure 處理失敗: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print("\n" + "=" * 60)
    print("測試完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_ppstructure()
