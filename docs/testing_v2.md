# 測試策略 (Testing Strategy V2)

> **版本**: VLM-First V2
> **日期**: 2026-02-17
> **狀態**: 規劃中 (Planned)

本文件定義針對 VLM-First 架構的測試策略。由於核心邏輯依賴外部 VLM API (Gemini)，測試重點將從「單元邏輯覆蓋」轉向「整合測試」與「驗證機制」。

---

## 1. 測試層級

### Level 1: 單元測試 (Unit Tests)
針對**確定性邏輯**進行測試，不依賴外部 API。

- **目標模組**:
  - `backend/processing/python_validator.py`: 驗算邏輯 (Math, Date parsing)。
  - `backend/processing/qr_handler.py`: QR 解碼邏輯 (Mock image input)。
  - `backend/engine/core.py`: 任務佇列管理、狀態轉換。
  - `backend/repositories/*`: 資料庫 CRUD 操作。

### Level 2: 整合測試 (Integration Tests)
針對 API 端點與資料流進行測試。

- **目標**: 確保 API 介面符合契約，且能正確觸發 Engine。
- **工具**: `TestClient` (FastAPI)。
- **Mocking**: 必須 Mock 掉 `VisionHandler` 的外部 API 呼叫，避免消耗額度與不確定性。

### Level 3: VLM 驗證 (VLM Verification)
針對 VLM 識別能力的評估。

- **方法**: 維護一個 **Golden Set** (包含標準發票、手寫收據、模糊照片)。
- **指標**: 比較 VLM 輸出與人工標註的 Ground Truth。
- **頻率**: 僅在更換 Model 或 Prompt 時執行。

---

## 2. 測試環境

- **Framework**: `pytest`
- **Mocking**: `unittest.mock`
- **Env**: 使用 `TESTing` 環境變數隔離資料庫 (避免汙染 `global_projects.db`)。

---

## 3. 遷移計畫

舊有的 `tests/` 目錄中包含大量針對 PaddleOCR 與舊架構的測試，需逐步替換。

1. **清理**: 移除 `test_rapidocr.py`, `test_paddle.py` 等過時檔案。
2. **新建**:
   - `tests/unit/test_validator.py`
   - `tests/unit/test_repos.py`
   - `tests/integration/test_api_jobs.py`
3. **Mocking**: 建立 `MockVisionHandler` 用於測試 Pipeline。
