# Codebase Cleanup and Optimization Plan

> **Status**: Planning
> **Date**: 2026-02-04
> **Goal**: Remove unused components and configurations following the migration to Gemini 2.5 Flash Lite, specifically removing local VLM dependencies while preserving local LLM text processing capabilities.

## Analysis of Unused Components

### 1. Vision System
- **Current State**: `VisionHandler` now uses Google Gemini API exclusively.
- **Obsolete**: 
    - Any lingering references to local Qwen-VL or Ollama for **vision** tasks.
    - `gemma_settings` in `config.json` (Gemma 3 4b) if it was intended for vision or unused experiments.

### 2. Configuration (`config.json`)
- **Action**: Remove `gemma_settings` if confirmed unused.
- **Action**: Check if `vision_settings` still has unused keys (e.g., `model_name` referring to local models if any default exists elsewhere).

### 3. Dependencies
- **Action**: Review `requirements.txt` or environment spec (if exists) to remove libraries that were *only* for local VLM if they differ from LLM requirements. (Note: `ollama` is still used for `LLMHandler`, so it must remain).

### 4. File Usage Analysis
- **`python_validator.py`**: **KEEP**. Used in `ReceiptProcessor` (Step 4) for logic-based validation.
- **`audit_handler.py`**: **DELETE/ARCHIVE**. Not imported or used in `ReceiptProcessor`. Seems to be an experimental or abandoned component.
- **`image_preprocessor.py`**: **KEEP**. Used in `ReceiptSplitter`.
- **`contour_validator.py`**: **KEEP**. Used in `ReceiptSplitter`.
- **`perspective_transform.py`**: **KEEP**. Used in `ReceiptSplitter`.
- **`receipt_virtual_ocr.py`**: **DELETE**. User verified this is obsolete in the new design. `receipt_processor.py` imports it (lines 176-221), needs refactoring.

## Proposed Changes

### Configuration Cleanup

#### [MODIFY] [config.json](file:///c:/Users/tange/Desktop/all_project/py/for/NKNU/GA/AI_AGENT_LAB/config.json)
- Remove `gemma_settings` block (lines 31-37).

### File Cleanup

#### [DELETE] Unused Files
| File | Reason |
|------|--------|
| `backend/processing/audit_handler.py` | No imports found in codebase |
| `backend/processing/receipt_virtual_ocr.py` | User confirmed obsolete |

### Code Refactoring

#### [MODIFY] [receipt_processor.py](file:///c:/Users/tange/Desktop/all_project/py/for/NKNU/GA/AI_AGENT_LAB/backend/processing/receipt_processor.py)
- **Lines 176-179**: Remove `from backend.processing.receipt_virtual_ocr import` block.
- **Lines 204-228**: Simplify `process_ocr_only` to use `to_plain_text()` for **all** receipt types (remove handwritten-specific virtual region formatting).

## Verification Plan

### Automated Verification
1. **Run `test_vision.py`**: Ensures `VisionHandler` (Gemini) still works after config changes.
   ```
   micromamba run -n OCR_GA python test_vision.py
   ```
2. **Run `receipt_processor.py` main block** (if available):
   ```
   micromamba run -n OCR_GA python -c "from backend.processing.receipt_processor import ReceiptProcessor; print('Import OK')"
   ```

### Manual Verification (User)
- After cleanup, upload a handwritten receipt via the UI and verify the pipeline completes without errors.

---

## Summary

| Action | Target | Status |
|--------|--------|--------|
| Delete | `audit_handler.py` | ✅ Done |
| Delete | `receipt_virtual_ocr.py` | ✅ Done |
| Remove | `gemma_settings` from `config.json` | ✅ Done |
| Refactor | `receipt_processor.py` (remove virtual_ocr usage) | ✅ Done |
