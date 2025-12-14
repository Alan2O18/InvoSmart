# backend/processing/ppstructure_handler.py
"""
PP-Structure Handler - Advanced Document Analysis

This module integrates PP-StructureV3 for structured document analysis.
"""
import os
import logging
import numpy as np
import cv2
import json
from markdownify import markdownify as md
from opencc import OpenCC

# Set environment variable to bypass potential network checks or blocking source checks
os.environ["DISABLE_MODEL_SOURCE_CHECK"] = "True"

logger = logging.getLogger(__name__)

class PPStructureHandler:
    """
    Advanced OCR handler using PPStructureV3 for structured output.
    """

    def __init__(self, config: dict):
        self.config = config
        self.engine = None
        self.is_v3 = False
        self.fallback_ocr = False
        
        # Initialize OpenCC
        try:
            text_processing = config.get("text_processing", {})
            opencc_config = text_processing.get("opencc_config", "s2twp")
            if opencc_config.endswith('.json'):
                opencc_config = opencc_config[:-5]
            self.converter = OpenCC(opencc_config)
        except Exception as e:
            logger.error(f"Failed to initialize OpenCC: {e}")
            self.converter = None

    def _init_engine(self):
        """Lazy initialization of the OCR/Structure engine."""
        if self.engine:
            return

        logger.info("Initializing PPStructure Engine (Lazy Load)...")
        
        try:
            import paddleocr
            
            def init_v3(args):
                logger.debug(f"Attempting PPStructureV3 init with args: {args}")
                return paddleocr.PPStructureV3(**args)

            try:
                # Attempt 1: Safe arguments
                lang = 'ch'
                try:
                    self.engine = init_v3({"show_log": True, "lang": lang})
                    self.is_v3 = True
                    logger.info("PPStructureV3 initialized successfully (Standard Mode)")
                    return
                except Exception as e:
                    logger.warning(f"PPStructureV3 standard init failed: {e}")

                # Attempt 2: Minimal arguments
                try:
                    self.engine = init_v3({"lang": lang})
                    self.is_v3 = True
                    logger.info("PPStructureV3 initialized successfully (Minimal Mode)")
                    return
                except Exception as e:
                     logger.warning(f"PPStructureV3 minimal init failed: {e}")

                # Attempt 3: No arguments
                self.engine = paddleocr.PPStructureV3()
                self.is_v3 = True
                logger.info("PPStructureV3 initialized successfully (Default Mode)")
                
            except AttributeError:
                logger.warning("PPStructureV3 not found, trying PPStructure (v2)...")
                from paddleocr import PPStructure
                try:
                    self.engine = PPStructure(show_log=True, image_orientation=True)
                except:
                     self.engine = PPStructure(image_orientation=True)
                self.is_v3 = False 
                
        except Exception as e:
            logger.error(f"Failed to initialize PPStructure: {e}", exc_info=True)
            logger.warning("Falling back to standard PaddleOCR...")
            try:
                from paddleocr import PaddleOCR
                try:
                    self.engine = PaddleOCR(use_angle_cls=True, lang='ch')
                except:
                    self.engine = PaddleOCR(lang='ch')
                self.fallback_ocr = True
            except Exception as e2:
                logger.critical(f"Critical: Failed to initialize any OCR engine: {e2}")
                raise RuntimeError("OCR Engine initialization failed completely.")

    def do_ppstructure(self, image_array: np.ndarray) -> list:
        """Run the engine prediction."""
        self._init_engine()
        
        logger.debug(f"Running prediction (Structure: {not self.fallback_ocr}, V3: {self.is_v3})...")
        try:
            if self.fallback_ocr:
                result = self.engine.ocr(image_array, cls=True)
                return result[0] if result else []
            else:
                # V3 Prediction
                if self.is_v3 and hasattr(self.engine, 'predict'):
                    logger.debug("Using .predict()")
                    result_obj = self.engine.predict(image_array)
                else:
                    logger.debug("Using __call__")
                    result_obj = self.engine(image_array)

                # DEBUG LOGGING REMOVED to reduce clutter, assuming flow is correct based on previous logs
                
                # Handle Generator
                if hasattr(result_obj, '__iter__') and not isinstance(result_obj, (list, dict, str, np.ndarray)):
                     result_list = list(result_obj)
                else:
                     result_list = result_obj

                final_regions = []
                
                if isinstance(result_list, list):
                    if len(result_list) == 0:
                        return []
                        
                    first = result_list[0]
                    
                    try:
                        # Correct path for V3 Layout Parsing Result: parsing_res_list
                        # Check attribute first (LayoutParsingResultV2 object)
                        if hasattr(first, 'parsing_res_list'):
                            final_regions = first.parsing_res_list
                        # Check dict key
                        elif isinstance(first, dict) and 'parsing_res_list' in first:
                            final_regions = first['parsing_res_list']
                        # Check for other potential keys just in case
                        elif isinstance(first, dict) and ('res' in first and 'type' in first):
                            final_regions = result_list
                        elif isinstance(first, list):
                            final_regions = first
                        else:
                            # Fallback: maybe just iterate it?
                            pass
                            
                    except Exception as e:
                        logger.error(f"Error inspecting first item: {e}")

                logging.info(f"Extracted {len(final_regions)} regions")
                return final_regions

        except Exception as e:
            logger.error(f"Prediction failed: {e}", exc_info=True)
            return []

    def ppstructure_to_markdown(self, regions) -> str:
        """Convert structured regions to markdown."""
        if not regions:
            logger.warning("ppstructure_to_markdown received empty regions")
            return ""

        # Helper to safely get attribute or key
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        # Sort regions by vertical position (center Y)
        def get_center_y(region):
            try:
                bbox = get_val(region, 'bbox') or get_val(region, 'layout_bbox')
                if bbox and len(bbox) >= 4:
                     return (bbox[1] + bbox[3]) / 2
                return 0
            except:
                return 0

        try:
            regions = sorted(regions, key=get_center_y)
        except Exception as e:
            logger.warning(f"Sorting regions failed: {e}")

        markdown_parts = []
        
        for i, region in enumerate(regions):
            try:
                # Extract basic info using helper
                # Keys for LayoutBlock: label, content. For dict: type, res/text
                r_type = get_val(region, 'label') or get_val(region, 'type') or ''
                r_type = r_type.lower()
                
                # Content might be in 'content' (LayoutBlock) or 'res'/'rec_text' (dict)
                # For table, we look for html
                res = get_val(region, 'content') or get_val(region, 'res') or get_val(region, 'rec_text')
                
                # Special handling for Table HTML in LayoutBlock?
                # Usually LayoutBlock has 'html' attribute if it's a table?
                html_content = get_val(region, 'html')
                
                # Debug first item keys if object
                if i == 0:
                     logger.info(f"Region 0 Type: {type(region)}")
                     logger.info(f"Region 0 Dir: {dir(region)}")

                # Text handling
                text_content = ""
                
                if r_type == 'table':
                    # Priority: 1. explicit html attr, 2. html in res dict, 3. html string in res
                    raw_html = html_content
                    if not raw_html:
                        if isinstance(res, dict) and 'html' in res:
                            raw_html = res['html']
                        elif isinstance(res, str) and '<table' in res:
                            raw_html = res
                    
                    if raw_html:
                        try:
                            md_table = md(raw_html)
                            markdown_parts.append(md_table)
                        except:
                             markdown_parts.append(f"```html\n{raw_html}\n```")
                    else:
                        logger.warning(f"Table region found but no HTML content. Res: {res}")
                
                else: # Text, Title, Header, etc.
                     if isinstance(res, list): # List of dicts or strings
                          lines = []
                          for item in res:
                               if isinstance(item, dict): lines.append(item.get('text', ''))
                               elif isinstance(item, str): lines.append(item)
                          text_content = " ".join(lines)
                     elif isinstance(res, dict): # Sometimes res is dict with 'text'?
                          text_content = res.get('text', '')
                     elif isinstance(res, str):
                          text_content = res
                     
                     if r_type in ['title', 'doc_title', 'section_header']:
                          text_content = f"## {text_content}"
                     
                     if text_content and text_content.strip():
                          markdown_parts.append(text_content)

            except Exception as e:
                logger.error(f"Error processing region {i}: {e}")
                continue

        return "\n\n".join(markdown_parts)

    def ocr_to_markdown(self, ocr_result) -> str:
        """Convert basic OCR result (fallback) to simple markdown."""
        if not ocr_result:
            return ""
        lines = []
        for line in ocr_result:
            try:
                text = line[1][0]
                lines.append(text)
            except:
                continue
        return "\n".join(lines)

    def convert_to_traditional(self, text: str) -> str:
        """Convert text to Traditional Chinese."""
        if not text or not self.converter:
            return text
        try:
            return self.converter.convert(text)
        except Exception as e:
            logger.error(f"Conversion failed: {e}")
            return text

    def process_receipt(self, image_array: np.ndarray) -> str:
        """Main entry point."""
        try:
            result = self.do_ppstructure(image_array)
            if not result:
                logger.warning("do_ppstructure returned empty result")
                return ""

            if self.fallback_ocr:
                md_text = self.ocr_to_markdown(result)
            else:
                md_text = self.ppstructure_to_markdown(result)

            logger.info(f"Generated Markdown length: {len(md_text)}")
            
            final_text = self.convert_to_traditional(md_text)
            return final_text

        except Exception as e:
            logger.error(f"process_receipt failed: {e}", exc_info=True)
            return ""

# Test block
if __name__ == "__main__":
    handler = PPStructureHandler({"ocr_settings": {}})
    print("Handler initialized.")
