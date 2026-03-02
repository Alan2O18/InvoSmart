# backend/engine/voucher_generator.py
import os
import logging
import fitz  # PyMuPDF
from typing import List

logger = logging.getLogger(__name__)

class VoucherGenerator:
    """
    產生「憑證黏貼用紙」的 PDF 整理報表。
    將處理完成的發票圖片，自動縮放並貼上範本下方的空白區域。
    """
    
    def __init__(self, template_path: str):
        self.template_path = template_path
        
        if not os.path.exists(template_path):
            logger.warning(f"[VoucherGenerator] 找不到範本路徑 {template_path}，匯出時可能失敗")

    def generate_voucher_pdf(self, image_paths: List[str], output_path: str) -> bool:
        """
        產生憑證黏貼 PDF
        :param image_paths: 需要貼上的發票/收據圖片絕對路徑清單
        :param output_path: 產生的 PDF 儲存路徑
        """
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Missing template PDF: {self.template_path}")
            
        if not image_paths:
            logger.warning("沒有提供任何圖片進行產生")
            return False
            
        try:
            doc = fitz.open(self.template_path)
            # 取得範本第一頁
            template_page = doc[0]
            
            # 定義可黏貼的區域 (A4 大小約 595 x 842 pts)
            # 根據範本，下半部是發票黏貼處，大約從 y=350 到 y=800
            paste_area = fitz.Rect(50, 350, 545, 800)
            
            # 準備輸出的文件
            out_doc = fitz.Document()
            
            for img_path in image_paths:
                if not os.path.exists(img_path):
                    logger.warning(f"圖片不存在，跳過: {img_path}")
                    continue
                    
                # 複製一頁新的範本出來 (先在 out_doc 開新頁，然後把 template 內容放進去)
                # 最穩定的做法：從 template doc copy
                out_doc.insert_pdf(doc, from_page=0, to_page=0)
                
                # 取得剛剛加進去的最新那一頁
                current_page = out_doc[-1]
                
                # 算出圖片本身的比例來決定 fitz.Rect，避免圖片變形
                img = fitz.Pixmap(img_path)
                img_w, img_h = img.width, img.height
                
                # 依寬度或高度做縮放，保持比例
                scale = min(paste_area.width / img_w, paste_area.height / img_h)
                
                # 不放大超過原始尺寸，但也不人為縮小
                scale = min(scale, 1.0)
                
                final_w = img_w * scale
                final_h = img_h * scale
                
                # 讓圖片盡量置中於下半部
                center_x = paste_area.x0 + paste_area.width / 2
                center_y = paste_area.y0 + paste_area.height / 2
                
                img_rect = fitz.Rect(
                    center_x - final_w / 2,
                    center_y - final_h / 2,
                    center_x + final_w / 2,
                    center_y + final_h / 2
                )
                
                # 把圖片貼上這頁
                current_page.insert_image(img_rect, filename=img_path)
            
            # 壓縮儲存
            out_doc.save(output_path, garbage=4, deflate=True)
            out_doc.close()
            doc.close()
            
            logger.info(f"成功生成憑證黏貼 PDF ({len(image_paths)} 頁) -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Generate voucher PDF failed: {e}", exc_info=True)
            raise e
