# backend/engine/voucher_generator.py
import os
import logging
import re
import random
from io import BytesIO
from pathlib import Path
import fitz  # PyMuPDF
from typing import List
from PIL import Image

from backend.engine.voucher_text_config import get_text_field_config, STAMP_ZONES, STITCHED_SEAL_CONFIG
from backend.processing.image_codec_adapter import ImageCodecAdapter
from backend.utils.stamp_ops import get_rotated_stamp_bytes

logger = logging.getLogger(__name__)


class VoucherGenerator:
    """
    產生「憑證黏貼用紙」的 PDF 整理報表。
    將處理完成的發票圖片，自動縮放並貼上範本下方的空白區域。
    """
    
    def __init__(self, template_path: str, font_path: str = ""):
        self.template_path = template_path
        self.font_path = font_path
        self.text_field_config = get_text_field_config()

        if self.font_path:
            resolved_font_path = str(Path(self.font_path).expanduser())
            if os.path.exists(resolved_font_path):
                self.font_path = resolved_font_path
            else:
                logger.warning("[VoucherGenerator] 找不到字型路徑 %s，改用內建字型", self.font_path)
                self.font_path = ""
        
        if not os.path.exists(template_path):
            logger.warning(f"[VoucherGenerator] 找不到範本路徑 {template_path}，匯出時可能失敗")

    @staticmethod
    def _safe_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF\w\s\-_/、，。,.:：※]", "", text)

    @staticmethod
    def _to_roc_date(pay_date: str) -> str:
        if not pay_date or not pay_date.strip():
            return ""
        match = re.search(r"^(\d{4})-(\d{2})-(\d{2})", pay_date)
        if not match:
            return ""
        year, month, day = match.groups()
        return f"{int(year) - 1911}/{month}/{day}"

    def _insert_text(self, page: fitz.Page, point: tuple[float, float], text: str, fontsize: int = 12):
        safe_text = self._safe_text(text)
        if not safe_text.strip():
            return
        page.insert_text(
            point,
            safe_text,
            fontsize=fontsize,
            fontname="F0" if self.font_path else "helv",
            fontfile=self.font_path if self.font_path else None,
        )

    def _insert_named_text(self, page: fitz.Page, field_name: str, text: str):
        config = self.text_field_config[field_name]
        if config.get("autoScale"):
            self._insert_autoscale_text(page, field_name, text)
            return
        safe_text = self._safe_text(text)
        max_chars = int(config.get("maxChars", 0))
        if max_chars > 0:
            safe_text = safe_text[:max_chars]
        self._insert_text(page, tuple(config["point"]), safe_text, fontsize=int(config["fontSize"]))

    def _insert_autoscale_text(self, page: fitz.Page, field_name: str, text: str, point_override: tuple[float, float] = None, fontsize_override: int = None):
        """Insert single-line text, shrinking font size until it fits within max_width."""
        config = self.text_field_config[field_name]
        safe_text = self._safe_text(text)
        max_chars = int(config.get("maxChars", 0))
        if max_chars > 0:
            safe_text = safe_text[:max_chars]
        if not safe_text.strip():
            return
        
        fontsize = fontsize_override if fontsize_override is not None else int(config["fontSize"])
        min_fontsize = int(config.get("minFontSize", int(config["fontSize"])))
        max_width = config.get("maxWidth")
        if max_width and fontsize > min_fontsize:
            max_width = float(max_width)
            with fitz.open() as scratch_doc:
                scratch_page = scratch_doc.new_page(width=595, height=842)
                for fs in range(fontsize, min_fontsize - 1, -1):
                    scratch_page.clean_contents()
                    scratch_page.insert_text(
                        (0, fs),
                        safe_text,
                        fontsize=fs,
                        fontname="F0" if self.font_path else "helv",
                        fontfile=self.font_path if self.font_path else None,
                    )
                    blocks = scratch_page.get_text("blocks")
                    actual_width = max((b[2] - b[0] for b in blocks), default=float("inf"))
                    if actual_width <= max_width:
                        fontsize = fs
                        break
                else:
                    fontsize = min_fontsize
        
        point_to_use = point_override if point_override is not None else tuple(config["point"])
        self._insert_text(page, point_to_use, safe_text, fontsize=fontsize)

    def _insert_multiline_named_text(self, page: fitz.Page, field_name: str, text: str):
        config = self.text_field_config[field_name]
        default_line_step = 17 if field_name == "voucherNo" else 20
        line_step = float(config.get("lineStep", default_line_step))
        
        x, y = tuple(config["point"])
        lines = str(text).replace("、", "\n").splitlines()
        
        base_fontsize = int(config["fontSize"])
        min_fontsize = int(config.get("minFontSize", base_fontsize))
        override_fontsize = base_fontsize
        
        if field_name == "voucherNo":
            excess = max(0, len(lines) - 4)
            if excess > 0:
                reduce_amount = excess * 2
                override_fontsize = max(min_fontsize, base_fontsize - reduce_amount)
                # Keep line spacing strictly proportional to the smaller font size
                line_step = line_step * (override_fontsize / float(base_fontsize)) if base_fontsize > 0 else line_step
        else:
            default_max_lines = 0
            max_lines = int(config.get("maxLines", default_max_lines))
            if max_lines > 0 and len(lines) > max_lines:
                lines = lines[:max_lines]

        for line_index, line in enumerate(lines):
            point = (x, y + (line_index * line_step))
            if config.get("autoScale"):
                self._insert_autoscale_text(page, field_name, line, point_override=point, fontsize_override=override_fontsize)
            else:
                self._insert_text(page, point, line, fontsize=override_fontsize)

    @staticmethod
    def _format_payment_amount(amount: str) -> str:
        if not amount or not str(amount).isdigit():
            return ""
        return f"{int(amount):,}元整"

    def _insert_purpose(self, page: fitz.Page, purpose: str):
        safe_text = self._safe_text(purpose)
        if not safe_text.strip():
            return

        config = self.text_field_config["purpose"]
        rect = fitz.Rect(*config["rect"])
        chosen_fontsize = int(config["fontSize"])
        chosen_text = safe_text
        truncated = False
        min_fontsize = int(config.get("minFontSize", chosen_fontsize))
        truncate_at = int(config.get("truncateAt", 80))
        truncate_suffix = str(config.get("truncateSuffix", "...(略)"))

        # Measure on a scratch page to avoid double-writing on the real page
        with fitz.open() as scratch_doc:
            scratch_page = scratch_doc.new_page(width=595, height=842)
            fontsize = chosen_fontsize
            while fontsize >= min_fontsize:
                remaining = scratch_page.insert_textbox(
                    rect,
                    safe_text,
                    fontsize=fontsize,
                    fontname="F0" if self.font_path else "helv",
                    fontfile=self.font_path if self.font_path else None,
                )
                if remaining >= 0:
                    chosen_fontsize = fontsize
                    break
                fontsize -= 1
            else:
                # All font sizes exhausted — truncate
                chosen_fontsize = min_fontsize
                chosen_text = safe_text[:truncate_at] + truncate_suffix
                truncated = True

        # Write once on the real page
        page.insert_textbox(
            rect,
            chosen_text,
            fontsize=chosen_fontsize,
            fontname="F0" if self.font_path else "helv",
            fontfile=self.font_path if self.font_path else None,
        )
        if truncated:
            logger.warning("Purpose text truncated during voucher rendering")

    def _insert_amount_cells(self, page: fitz.Page, amount: str):
        if not amount or not str(amount).isdigit():
            return
        config = self.text_field_config["amount"]
        pad_length = int(config.get("padLength", 6))
        pad_char = str(config.get("padChar", "※"))
        amount_text = str(int(amount))
        y = float(config["y"])
        x_list = list(config["xList"])
        font_size = int(config["fontSize"])
        if len(amount_text) > len(x_list):
            raise ValueError(f"Amount '{amount_text}' exceeds voucher amount cells ({len(x_list)})")
        text = amount_text.rjust(pad_length, pad_char)
        for idx, char in enumerate(text[:len(x_list)]):
            self._insert_text(page, (x_list[idx], y), char, fontsize=font_size)

    @staticmethod
    def _image_stream_from_pil(image: Image.Image, target_width_pts: float) -> bytes:
        image = image.convert("RGB")
        target_px = int((target_width_pts / 72.0) * 300)
        target_px = max(1, min(target_px, image.width))
        if target_px < image.width:
            target_h = max(1, int((target_px / image.width) * image.height))
            image = image.resize((target_px, target_h), Image.Resampling.LANCZOS)

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()

    @staticmethod
    def _image_stream_for_rect(image_path: str, target_width_pts: float) -> bytes:
        image = ImageCodecAdapter().read_image_pil(image_path)
        return VoucherGenerator._image_stream_from_pil(image, target_width_pts)

    @staticmethod
    def _render_missing_marker(page: fitz.Page, rect: fitz.Rect):
        page.draw_rect(rect, color=(1, 0, 0), width=2)
        page.draw_line(rect.tl, rect.br, color=(1, 0, 0), width=2)
        page.draw_line(rect.tr, rect.bl, color=(1, 0, 0), width=2)
        page.insert_text((rect.x0 + 4, rect.y0 + 14), "圖片損壞無法載入", fontsize=10, color=(1, 0, 0))

    @staticmethod
    def _get_rotated_stamp_bytes_wrapper(stamp_path: str, max_angle: int = 10) -> bytes | None:
        """
        Read stamp image, rotate it, and preserve alpha channel.
        """
        if not stamp_path or not os.path.exists(stamp_path):
            logger.warning(f"[Stamp] 印章文件不存在: {stamp_path}")
            return None
        
        try:
            return get_rotated_stamp_bytes(stamp_path, max_angle=max_angle)
        except Exception as exc:
            logger.warning(f"[Stamp] 讀取/旋轉印章文件失敗 {stamp_path}: {exc}")
            return None

    @staticmethod
    def _insert_stamp(page: fitz.Page, stamp_bytes: bytes, rect: fitz.Rect):
        """
        Insert stamp image into PDF at specified rectangle.
        The image should already be rotated if needed.
        """
        if not stamp_bytes:
            return
        
        try:
            page.insert_image(rect, stream=stamp_bytes)
            logger.debug(f"[Stamp] 印章已插入")
        except Exception as exc:
            logger.warning(f"[Stamp] 插入印章失敗: {exc}")

    def _apply_stamps_to_page(self, page: fitz.Page, stamps: dict[str, str | None], img_rects: list[fitz.Rect] | None = None):
        """
        Apply all stamps (static and stitched seals) to the page.
        
        Args:
            page: PyMuPDF page object
            stamps: Dictionary mapping role names to image file paths
            img_rects: Optional list of image rectangles for stitched seal placement
        """
        if not stamps:
            return
        
        # Apply static stamps (角色章)
        for role, stamp_path in stamps.items():
            if role in ("fin_original", "fin_audited"):
                # Skip stitched seals here, handled separately
                continue
            
            if not stamp_path:
                logger.debug(f"[Stamp] 角色 '{role}' 無可用印章，跳過")
                continue
            
            if role not in STAMP_ZONES:
                logger.warning(f"[Stamp] 角色 '{role}' 未定義蓋章位置，跳過")
                continue
            
            zone_config = STAMP_ZONES[role]
            rect_data = zone_config["rect"]
            rect = fitz.Rect(rect_data[0], rect_data[1], rect_data[0] + rect_data[2], rect_data[1] + rect_data[3])
            
            stamp_bytes = self._get_rotated_stamp_bytes_wrapper(stamp_path)
            if stamp_bytes:
                self._insert_stamp(page, stamp_bytes, rect)
        
        # Apply stitched seals (騎縫章) on image edges
        if img_rects:
            for img_rect in img_rects:
                # 與正本相符 - on right edge
                if stamps.get("fin_original"):
                    seal_config = STITCHED_SEAL_CONFIG["fin_original"]
                    seal_bytes = self._get_rotated_stamp_bytes_wrapper(stamps["fin_original"])
                    if seal_bytes:
                        # Position on right edge of image
                        edge_offset = seal_config.get("edge_offset", 5)
                        seal_rect = fitz.Rect(
                            img_rect.x1 - 20, img_rect.y0,
                            img_rect.x1 + 20, img_rect.y0 + 40
                        )
                        self._insert_stamp(page, seal_bytes, seal_rect)
                
                # 已稽核 - on left edge
                if stamps.get("fin_audited"):
                    seal_config = STITCHED_SEAL_CONFIG["fin_audited"]
                    seal_bytes = self._get_rotated_stamp_bytes_wrapper(stamps["fin_audited"])
                    if seal_bytes:
                        # Position on left edge of image
                        edge_offset = seal_config.get("edge_offset", -5)
                        seal_rect = fitz.Rect(
                            img_rect.x0 - 20, img_rect.y0,
                            img_rect.x0 + 20, img_rect.y0 + 40
                        )
                        self._insert_stamp(page, seal_bytes, seal_rect)

    def generate_from_layout(self, pages: List[dict], job_image_map: dict[str, str], output_path: str, stamps: dict[str, str | None] | None = None) -> bool:
        """
        Generate PDF from layout with optional stamp application.
        
        Args:
            pages: List of page payloads with fields and images
            job_image_map: Mapping from job_id to image file paths
            output_path: Output PDF path
            stamps: Dictionary mapping role names to stamp image file paths
        """
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"Missing template PDF: {self.template_path}")

        with fitz.open(self.template_path) as template_doc:
            with fitz.open() as out_doc:
                for page_payload in pages:
                    images = page_payload.get("images", [])
                    if not images:
                        continue

                    out_doc.insert_pdf(template_doc, from_page=0, to_page=0)
                    page = out_doc[-1]

                    fields = page_payload.get("fields", {})
                    self._insert_multiline_named_text(page, "voucherNo", str(fields.get("voucherNo", "")))
                    self._insert_named_text(page, "budgetItem", str(fields.get("budgetItem", "")))
                    self._insert_amount_cells(page, str(fields.get("amount", "")))
                    self._insert_purpose(page, str(fields.get("purpose", "")))
                    self._insert_named_text(page, "receiptCount", str(fields.get("receiptCount", "")))
                    self._insert_named_text(page, "payDate", self._to_roc_date(str(fields.get("payDate", ""))))
                    self._insert_named_text(page, "paymentAmount", self._format_payment_amount(str(fields.get("amount", ""))))

                    # Track image rectangles for stitched seal placement
                    img_rects: list[fitz.Rect] = []
                    
                    for image in images:
                        job_id = image.get("jobId")
                        x = float(image.get("x", 0))
                        y = float(image.get("y", 0))
                        w = float(image.get("w", 0))
                        h = float(image.get("h", 0))
                        rect = fitz.Rect(x, y, x + w, y + h)
                        img_rects.append(rect)

                        image_path = job_image_map.get(job_id)
                        if not image_path or not os.path.exists(image_path):
                            self._render_missing_marker(page, rect)
                            continue

                        image_stream = self._image_stream_for_rect(image_path, w)
                        page.insert_image(rect, stream=image_stream)
                    
                    # Apply stamps (static and stitched seals)
                    if stamps:
                        self._apply_stamps_to_page(page, stamps, img_rects)

                if out_doc.page_count == 0:
                    out_doc.insert_pdf(template_doc, from_page=0, to_page=0)

                out_doc.save(output_path, deflate=True, garbage=4)

        return True

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
            codec = ImageCodecAdapter()
            
            # 定義可黏貼的區域 (A4 大小約 595 x 842 pts)
            # 根據範本，下半部是發票黏貼處，大約從 y=350 到 y=800
            paste_area = fitz.Rect(50, 350, 545, 800)
            with fitz.open(self.template_path) as doc:
                with fitz.open() as out_doc:
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
                        image = codec.read_image_pil(img_path)
                        img_w, img_h = image.width, image.height

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
                        image_stream = self._image_stream_from_pil(image, final_w)
                        current_page.insert_image(img_rect, stream=image_stream)

                    # 壓縮儲存
                    out_doc.save(output_path, garbage=4, deflate=True)
            
            logger.info(f"成功生成憑證黏貼 PDF ({len(image_paths)} 頁) -> {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Generate voucher PDF failed: {e}", exc_info=True)
            raise e
