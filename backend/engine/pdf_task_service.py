import fitz  # PyMuPDF
import logging
import base64
from pathlib import Path
from typing import List, Optional, Literal
import cv2
import numpy as np
from backend.repositories.pdf_task_repo import PdfTaskRepository
from backend.utils.stamp_ops import get_rotated_stamp_bytes

logger = logging.getLogger(__name__)

class PdfTaskService:
    def __init__(self, pdf_task_repo: PdfTaskRepository, stamp_template_repo=None):
        self.pdf_task_repo = pdf_task_repo
        self.stamp_template_repo = stamp_template_repo

    def get_template_preview_payload(self, template_path: str | Path) -> dict:
        try:
            with fitz.open(str(template_path)) as doc:
                page = doc[0]
                pix = page.get_pixmap(dpi=144)
                return {
                    "templatePng": base64.b64encode(pix.tobytes("png")).decode("utf-8"),
                    "pageWidth": float(page.rect.width),
                    "pageHeight": float(page.rect.height),
                    "previewPixelWidth": int(pix.width),
                    "previewPixelHeight": int(pix.height),
                }
        except Exception as e:
            logger.error(f"Failed to render template preview: {e}")
            raise e

    def get_pdf_page_count(self, pdf_path: str | Path) -> int:
        try:
            with fitz.open(pdf_path) as doc:
                return doc.page_count
        except Exception as e:
            logger.error(f"Failed to read page count of PDF {pdf_path}: {e}")
            return 0

    def apply_stamp(
        self,
        task_id: str,
        stamp_path: Path,
        rect_data: dict,
        mode: Literal["single", "full"],
        page_index: int = 0,
    ) -> int:
        pdf_path = self.pdf_task_repo._task_pdf_path(task_id)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        try:
            page_count = doc.page_count
            if mode == "full":
                page_indices = range(page_count)
            else:
                page_indices = [max(0, min(page_index, page_count - 1))]

            for idx in page_indices:
                page = doc[idx]
                rect = fitz.Rect(
                    float(rect_data.get("x", page.rect.width * 0.68)),
                    float(rect_data.get("y", page.rect.height * 0.72)),
                    float(rect_data.get("x", page.rect.width * 0.68)) + float(rect_data.get("w", page.rect.width * 0.22)),
                    float(rect_data.get("y", page.rect.height * 0.72)) + float(rect_data.get("h", page.rect.height * 0.18)),
                )
                stamp_bytes = get_rotated_stamp_bytes(str(stamp_path))
                page.insert_image(rect, stream=stamp_bytes, keep_proportion=True, overlay=True)

            doc.save(pdf_path, deflate=True, garbage=4, clean=True)
            return doc.page_count
        finally:
            doc.close()

    def compress_pdf(self, task_id: str) -> None:
        pdf_path = self.pdf_task_repo._task_pdf_path(task_id)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        try:
            doc.save(pdf_path, deflate=True, garbage=4, clean=True)
        finally:
            doc.close()

    def execute_page_operations(
        self,
        task_id: str,
        operation: Literal["delete", "reorder", "add"],
        page_indices: List[int],
        page_order: Optional[List[int]],
        insert_count: int = 1,
    ) -> int:
        pdf_path = self.pdf_task_repo._task_pdf_path(task_id)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        doc = fitz.open(pdf_path)
        try:
            if operation == "delete":
                for page_index in sorted(set(page_indices), reverse=True):
                    if 0 <= page_index < doc.page_count:
                        doc.delete_page(page_index)
            elif operation == "reorder":
                order = page_order or []
                if sorted(order) != list(range(doc.page_count)):
                    raise ValueError("page_order must contain each page index exactly once")
                reordered = fitz.open()
                for page_index in order:
                    reordered.insert_pdf(doc, from_page=page_index, to_page=page_index)
                doc.close()
                doc = reordered
            elif operation == "add":
                for _ in range(max(1, insert_count)):
                    doc.new_page(-1)
            else:
                raise ValueError(f"Unsupported page operation: {operation}")

            doc.save(pdf_path, deflate=True, garbage=4, clean=True)
            return doc.page_count
        finally:
            doc.close()

    @staticmethod
    def render_pdf_first_page_to_bgr(pdf_path: str) -> np.ndarray:
        with fitz.open(pdf_path) as doc:
            if doc.page_count <= 0:
                raise ValueError("PDF has no pages")
            page = doc[0]
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=zoom_matrix)

        img_data = pix.samples
        if pix.n == 4:
            img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.h, pix.w, 4)
            return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)

        img_array = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
