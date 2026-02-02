"""
Receipt Virtual Region Formatter
收據虛擬分區格式化工具

根據 OCR 結果的座標將文字分配到各虛擬區域：
- 買受人 (左上)
- 日期 (右上)
- 品項表格 (左側)
- 店章 (右側)
- 合計 (底部)

注意：此模組不執行 OCR，只負責分區和格式化。
OCR 由 RapidOCRHandler 在 receipt_processor.process_ocr_only() 中執行。
"""

from typing import Dict, List, Any


# ==========================================
# 配置
# ==========================================

# 虛擬區域邊界 (相對比例)
REGION_BOUNDARIES = {
    'header_ratio': 0.28,    # 0-28% = 頂部區 (買受人/日期)
    'main_ratio': 0.88,      # 28-88% = 主體區 (表格/店章)
    'left_ratio': 0.70,      # 左側佔 70%
    # 88-100% = 底部 (合計)
}


# ==========================================
# 虛擬分區
# ==========================================

def classify_text_to_regions(
    ocr_results: List,
    image_height: int,
    image_width: int
) -> Dict[str, List[Dict]]:
    """
    根據座標將 OCR 結果分類到虛擬區域
    
    Args:
        ocr_results: RapidOCR 返回的結果 [[四角點], 文字, 信心度]
        image_height: 圖片高度
        image_width: 圖片寬度
        
    Returns:
        各區域的文字列表
    """
    regions = {
        'buyer': [],
        'date': [],
        'table': [],
        'stamp': [],
        'summary': []
    }
    
    # 計算邊界像素值
    header_y = int(image_height * REGION_BOUNDARIES['header_ratio'])
    main_y = int(image_height * REGION_BOUNDARIES['main_ratio'])
    mid_x = int(image_width * REGION_BOUNDARIES['left_ratio'])
    
    for item in ocr_results:
        box_points, text, confidence = item
        
        # 計算文字區塊的中心點
        xs = [p[0] for p in box_points]
        ys = [p[1] for p in box_points]
        center_x = sum(xs) / 4
        center_y = sum(ys) / 4
        
        # 創建結構化資料
        text_item = {
            'text': text,
            'confidence': float(confidence),
            'center': (center_x, center_y),
            'box': [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
        }
        
        # 根據位置分類
        if center_y < header_y:
            # 頂部區
            if center_x < mid_x:
                regions['buyer'].append(text_item)
            else:
                regions['date'].append(text_item)
        elif center_y < main_y:
            # 主體區
            if center_x < mid_x:
                regions['table'].append(text_item)
            else:
                regions['stamp'].append(text_item)
        else:
            # 底部區
            regions['summary'].append(text_item)
    
    # 按 Y 座標排序每個區域的文字
    for region_name in regions:
        regions[region_name].sort(key=lambda x: x['center'][1])
    
    return regions



def format_regions_to_markdown(regions: Dict[str, List[Dict]]) -> str:
    """
    將分區結果格式化為 LLM 可理解的 Markdown
    
    策略：
    1. 按 Y 座標分組成「列」(較大容差)
    2. 同列內按 X 座標排序並合併
    3. 用正則過濾不需要的內容
    """
    import re
    import logging
    logger = logging.getLogger(__name__)
    
    # ===== DEBUG: 輸出原始 OCR 結果 (未過濾) =====
    logger.info("="*60)
    logger.info("[VirtualOCR] 原始 OCR 結果 (過濾前):")
    for region_name, items in regions.items():
        if items:
            sorted_items = sorted(items, key=lambda x: x['center'][1])
            logger.info(f"  [{region_name}] ({len(items)} 項):")
            for it in sorted_items:
                logger.info(f"    [{int(it['center'][0]):4d},{int(it['center'][1]):4d}] \"{it['text']}\"")
    logger.info("="*60)
    
    # ===== 輔助函數：按 Y 座標分組成列 =====
    def group_into_rows(items: List[Dict], y_threshold: int = 40) -> List[List[Dict]]:
        """將項目按 Y 座標分組成列"""
        if not items:
            return []
        
        sorted_items = sorted(items, key=lambda x: x['center'][1])
        rows = []
        current_row = []
        current_y = -1000
        
        for item in sorted_items:
            y = item['center'][1]
            if abs(y - current_y) > y_threshold:
                if current_row:
                    rows.append(current_row)
                current_row = [item]
                current_y = y
            else:
                current_row.append(item)
        
        if current_row:
            rows.append(current_row)
        
        return rows
    
    def row_to_text(row: List[Dict]) -> str:
        """將一列項目按 X 座標排序後合併為文字"""
        sorted_row = sorted(row, key=lambda x: x['center'][0])
        return " ".join([item['text'] for item in sorted_row])
    
    # ===== 過濾用正則 =====
    # 買受人區要過濾的關鍵字
    BUYER_FILTER = re.compile(r'免用統一發票|地址|中華民國|統一編號|統一福号|數量|品名|單價|總價|品\s*價')
    
    # 合計區白名單：只保留這些
    SUMMARY_WHITELIST = re.compile(r'合計|合计|新台幣|新台币|萬|仟|千|佰|百|拾|十|元|整|'
                                   r'壹|貳|參|肆|伍|陸|柒|捌|玖|零|'
                                   r'一|二|三|四|五|六|七|八|九|〇|'
                                   r'\d')
    
    # 要過濾掉的雜訊字符 (劃線防竄改)
    NOISE_CHARS = re.compile(r'^[-一—X×xXＸ]+$|^[/\\\|]+$')
    
    lines = []
    lines.append("# 手寫收據 OCR 辨識結果")
    lines.append("")
    
    # ===== 買受人區 (左上) =====
    buyer_items = regions.get('buyer', [])
    if buyer_items:
        lines.append("## 買受人")
        
        # 先過濾個別項目，再聚合
        BUYER_ITEM_FILTER = re.compile(r'免用統一發票|免用统一發票|地址|中華民國|統一編號|统一编号|统一福号|數量|品名|單價|總價')
        filtered_items = [
            item for item in buyer_items 
            if not BUYER_ITEM_FILTER.search(item['text'])
        ]
        
        if filtered_items:
            rows = group_into_rows(filtered_items, y_threshold=35)
            for row in rows:
                row_text = row_to_text(row)
                if row_text.strip():
                    lines.append(row_text)
        
        lines.append("")
    
    # ===== 日期區 (右上) =====
    date_items = regions.get('date', [])
    if date_items:
        lines.append("## 日期")
        rows = group_into_rows(date_items, y_threshold=35)
        
        date_texts = []
        for row in rows:
            row_text = row_to_text(row)
            # 過濾掉不含日期相關字符的
            if re.search(r'\d|年|月|日', row_text):
                # 去掉「中華民國」前綴，保留數字
                cleaned = re.sub(r'中華民國', '', row_text).strip()
                if cleaned:
                    date_texts.append(cleaned)
        
        if date_texts:
            lines.append(" ".join(date_texts))
        lines.append("")
    
    # ===== 品項表格區 (左側) =====
    table_items = regions.get('table', [])
    if table_items:
        lines.append("## 品項明細")
        lines.append("")
        
        # 使用較大容差分組 (手寫字行距較大)
        rows = group_into_rows(table_items, y_threshold=45)
        
        for row in rows:
            # 同列內按 X 座標排序
            sorted_row = sorted(row, key=lambda x: x['center'][0])
            row_texts = [item['text'] for item in sorted_row]
            
            # 過濾純雜訊
            row_texts = [t for t in row_texts if not NOISE_CHARS.match(t)]
            if not row_texts:
                continue
            
            # 合併成一行
            row_str = " | ".join(row_texts)
            combined = "".join(row_texts)
            
            # 識別表頭行
            if re.search(r'品名|單價|數量|金額', combined):
                lines.append(f"**{row_str}**")
            elif len(row_texts) >= 2:
                # 多欄位，輸出為表格行
                lines.append(f"| {row_str} |")
            elif len(combined) >= 2:
                # 單項目
                lines.append(row_str)
        
        lines.append("")
    
    # ===== 店章區 (右側) =====
    stamp_items = regions.get('stamp', [])
    if stamp_items:
        lines.append("## 店家資訊")
        rows = group_into_rows(stamp_items, y_threshold=40)
        
        for row in rows:
            row_text = row_to_text(row)
            # 過濾太短或純符號
            if len(row_text) < 2:
                continue
            if NOISE_CHARS.match(row_text):
                continue
            lines.append(f"- {row_text}")
        
        lines.append("")
    
    # ===== 合計區 (底部) =====
    summary_items = regions.get('summary', [])
    if summary_items:
        lines.append("## 合計")
        rows = group_into_rows(summary_items, y_threshold=40)
        
        summary_parts = []
        for row in rows:
            row_text = row_to_text(row)
            
            # 過濾雜訊 (純符號線)
            if NOISE_CHARS.match(row_text):
                continue
            
            # DEBUG: 暫時停用白名單過濾，顯示原始結果
            # filtered_chars = []
            # for char in row_text:
            #     if SUMMARY_WHITELIST.search(char) or char in ' ':
            #         filtered_chars.append(char)
            # filtered_text = "".join(filtered_chars).strip()
            # if filtered_text:
            #     summary_parts.append(filtered_text)
            summary_parts.append(row_text)
        
        # 合併所有合計相關文字
        if summary_parts:
            lines.append(" ".join(summary_parts))
        
        lines.append("")
    
    return "\n".join(lines)

