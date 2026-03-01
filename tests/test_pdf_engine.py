import os
import fitz
import pytest
from pathlib import Path
from backend.processing.pdf_engine import (
    compress_pdf, reorder_pages, stamp_image, inject_text_layer, execute_commands, PDFEngineError
)

# Helper function to create a dummy PDF
def create_dummy_pdf(path: str, num_pages: int = 3):
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((50, 50), f"Dummy Page {i}")
    doc.save(path)
    doc.close()

# Helper function to create a dummy image
def create_dummy_image(path: str):
    import cv2
    import numpy as np
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[:] = (0, 0, 255) # Red square
    cv2.imwrite(path, img)

@pytest.fixture
def temp_workspace(tmp_path):
    pdf_path = str(tmp_path / "test.pdf")
    img_path = str(tmp_path / "stamp.png")
    out_path = str(tmp_path / "output.pdf")
    
    create_dummy_pdf(pdf_path)
    create_dummy_image(img_path)
    
    yield {"pdf": pdf_path, "img": img_path, "out": out_path, "dir": tmp_path}

def test_compress_pdf(temp_workspace):
    in_pdf = temp_workspace["pdf"]
    out_pdf = temp_workspace["out"]
    
    # Compress
    assert compress_pdf(in_pdf, out_pdf) == True
    assert os.path.exists(out_pdf)
    
    # Verify it's a valid PDF
    doc = fitz.open(out_pdf)
    assert doc.page_count == 3
    doc.close()

def test_reorder_pages(temp_workspace):
    in_pdf = temp_workspace["pdf"]
    doc = fitz.open(in_pdf)
    
    # Reorder fully
    reorder_pages(doc, [2, 0, 1])
    assert doc.page_count == 3
    assert "Dummy Page 2" in doc[0].get_text()
    assert "Dummy Page 0" in doc[1].get_text()
    assert "Dummy Page 1" in doc[2].get_text()
    
    # Delete pages (only keep one page)
    reorder_pages(doc, [1])
    assert doc.page_count == 1
    assert "Dummy Page 0" in doc[0].get_text()
    
    doc.close()

def test_stamp_image(temp_workspace):
    in_pdf = temp_workspace["pdf"]
    img_path = temp_workspace["img"]
    out_pdf = temp_workspace["out"]
    
    doc = fitz.open(in_pdf)
    rect = (100, 100, 200, 200)
    
    # Need to save the document after stamping to properly check image count in some fitz versions
    stamp_image(doc, 0, img_path, rect)
    doc.save(out_pdf)
    doc.close()
    
    doc2 = fitz.open(out_pdf)
    page = doc2[0]
    # Check if there's an image on the page
    images = page.get_images()
    assert len(images) > 0
    doc2.close()

def test_inject_text_layer(temp_workspace):
    in_pdf = temp_workspace["pdf"]
    out_pdf = temp_workspace["out"]
    
    doc = fitz.open(in_pdf)
    text_to_inject = "HIDDEN_SECRET_CODE"
    rect = (10, 10, 200, 50)
    
    inject_text_layer(doc, 0, text_to_inject, rect)
    doc.save(out_pdf)
    doc.close()
    
    # Verify the text is searchable
    doc2 = fitz.open(out_pdf)
    page = doc2[0]
    text = page.get_text()
    assert text_to_inject in text
    doc2.close()

def test_execute_commands_full_pipeline(temp_workspace):
    in_pdf = temp_workspace["pdf"]
    img_path = temp_workspace["img"]
    out_pdf = temp_workspace["out"]
    
    commands = {
        "page_order": [2, 1], # Reverse order and drop page 0
        "stamps": [
            {"page": 0, "image_path": img_path, "rect": [50, 50, 150, 150]}
        ],
        "texts": [
            {"page": 1, "text": "INVOICE_12345", "rect": [10, 10, 100, 30]}
        ]
    }
    
    assert execute_commands(in_pdf, out_pdf, commands) == True
    
    # Verify final PDF
    doc = fitz.open(out_pdf)
    assert doc.page_count == 2
    assert "Dummy Page 2" in doc[0].get_text() # Page 0 is now old Dummy Page 2
    assert len(doc[0].get_images()) > 0 # Stamp is on new Page 0
    assert "INVOICE_12345" in doc[1].get_text() # Text is on new Page 1
    doc.close()
