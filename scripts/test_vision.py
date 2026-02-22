#!/usr/bin/env python
"""Test VisionHandler with Gemini"""
import sys
import json
import cv2
import numpy as np

sys.path.insert(0, '.')
from backend.processing.vision_handler import VisionHandler

def cv_imread_chinese(file_path):
    """Read image with Chinese path support"""
    return cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), cv2.IMREAD_COLOR)

# Load config
with open('config.json', 'r', encoding='utf-8') as f:
    cfg = json.load(f)

# Load test image - use Chinese path helper
img_path = 'dev_data/test_images/手寫收據20251117_split_0_1766302781.jpg'
img = cv_imread_chinese(img_path)

if img is None:
    print(f"Error: Cannot read image {img_path}")
    sys.exit(1)

print(f"Image loaded: {img.shape}")

# Create handler
handler = VisionHandler(cfg)

# Process
print("Processing...")
result, stats = handler.process_handwritten(img)

print("\n" + "="*50)
print("RESULT:")
print("="*50)
print(result[:1000] if result else "(empty)")
print("\n" + "="*50)
print("STATS:")
print(json.dumps(stats, ensure_ascii=False, indent=2))
