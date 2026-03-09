# 測試策略 (Testing Strategy V2)

> **版本**: VLM-First V2
> **日期**: 2026-03-07
> **狀態**: 使用中 (Living Document)

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
- **Backend Env**: 使用既有 micromamba 環境 `OCR_GA`
- **Frontend Test Runner**: 目前以 Node 內建 test runner 與 Vite build 為主
- **Env**: 使用測試資料與 mock 隔離資料庫/外部 API，避免汙染正式資料

### 2.1 目前建議指令

```bash
micromamba activate OCR_GA
pytest tests/ -q
```

```bash
cd frontend
node --test tests/voucher-utils.test.js
npm run build
```

### 2.2 Voucher Editor 最低驗證範圍

Voucher Editor 涉及前端 Canvas、後端 route 驗證與 PDF 輸出，目前以「後端自動化 + 前端 build + 手動比對」為最實際的組合：

1. 後端 route 測試：`/api/voucher/{project_id}/generate`、`/api/voucher/fonts/kaiu.ttf`
2. 前端 utility 測試：日期解析、碰撞檢測、自動排版等純函式
3. 前端 build：確保 `VoucherEditorView.vue` 的改動可編譯
4. 手動驗證：Canvas 預覽、頁面切換、PDF 下載與版面對齊

### 2.3 V0.0.7 金額制度回歸重點

1. Strict amount 必須為純數字且 `<= 999999`（六格），`1000000` 應回 422。
2. `/api/voucher/text-config` 的 `fields.amount` 必須回傳六格 `xList` 與 `digitPolicy: 6`。
3. 前端 preview utilities 必須避免 `xList` 越界造成 Canvas `NaN` 座標崩潰。
4. `VoucherGenerator._insert_amount_cells` 對超過格數輸入應拋錯，禁止 silent truncation。

---

## 3. 遷移計畫

舊有的 `tests/` 目錄中包含大量針對 PaddleOCR 與舊架構的測試，需逐步替換。

1. **清理**: 移除 `test_rapidocr.py`, `test_paddle.py` 等過時檔案。
2. **新建**:
   - `tests/unit/test_validator.py`
   - `tests/unit/test_repos.py`
   - `tests/integration/test_api_jobs.py`
3. **Mocking**: 建立 `MockVisionHandler` 用於測試 Pipeline。

> **備註**: 實際專案目前仍保留部分歷史測試與相容層，例如 RapidOCR 相關測試。文件中的「清理」應視為持續整理方向，不代表現況已完全移除。
