# VLM Migration Plan: Gemini Flash Lite Implementation

> **Status**: Planning
> **Date**: 2026-02-04
> **Goal**: Replace local VLM with Google AI Studio's **Gemini 2.5 Flash Lite** (or latest available Flash model) for high-accuracy, cost-effective processing of handwritten receipts.

## 1. 核心決策 (Core Decisions)

1.  **Model Switch**: 從本地 VLM (Local Ollama/Qwen) 遷移至 **Google AI Studio (Gemini 2.5Flash Lite)**。
    *   *理由*: 免費額度足夠、速度快、對繁體中文與手寫辨識能力極強。
2.  **Strategy Change**: 採用 **"High Trust, Verify Later"** 策略。
    *   不再強制要求 LLM 使用 OCR 結果進行交叉比對 (Cross-Validation)。
    *   直接信任 VLM 輸出的 JSON 結果。
    *   依賴後續的「人工檢查 (Human Review)」機制來修正錯誤。
3.  **Hybrid Architecture**:
    *   **VLM (Vision)**: Cloud (Gemini) - 負責困難的手寫辨識。
    *   **LLM (Text)**: Local (Existing) - 負責一般的文字處理、RAG、或簡單的邏輯判斷 (保持現狀)。

---

## 2. 架構變更 (Architecture Changes)

### 2.1 `backend/processing/vision_handler.py` 重構

原本的設計是呼叫 Ollama，現在需要重寫為呼叫 Google Generative AI SDK。

*   **Remove**: Ollama dependence for vision tasks.
*   **Add**: `google-generativeai` library integration.
*   **Method**: `process_handwritten(image_array)` 將直接打 API 回傳 JSON。

### 2.2 處理流程更新 (Handwritten Flow)

**Old Plan:**
> VLM -> JSON + OCR -> Text -> LLM Merge & Verify

**New Plan:**
> Image -> **Gemini Flash Lite** -> JSON Structure -> Save -> (Human Review)

---

## 3. 實作細節 (Implementation Details)

### 3.1 環境設定 (Environment)

*   需要安裝 Python 套件: `google-generativeai`
*   環境變數: 需要 `GOOGLE_API_KEY`

### 3.2 Prompt Design (提示詞設計)

你是一個專業的台灣收據辨識助手。請辨識這張圖片中的手寫或印刷收據內容，並輸出為嚴格的 JSON 格式 (不要包含 Markdown code fence)。

請參考以下 JSON 範例輸出：
{
  "receipt_type": "免用統一發票收據",  
  "header": {
      "supplier": "預設店家名", 
      "buyer": "預設買受人", 
      "invoice_id": "", 
      "date": "中華民國1140930", 
  }, 
  "items": [
      {"name": "品項名稱", "qty": 1, "price": 100, "total": 100}
  ], 
  "summary": {
      "total": 100
  }, 
  "verification": {
      "handwritten_total_chinese": "壹仟元整", 
      "stamp_shop_name": "店家章名稱"
  }
}

規則：
1. "receipt_type": 依據圖片內容判斷，例如 "免用統一發票收據"、"電子發票證明聯" 等。
2. "date": 請轉換為 "中華民國YYYMMDD" 或 "YYYY-MM-DD" 格式。
3. "items": 請列出所有品項，確保 "total" = "qty" * "price"。
4. "summary.total": 必須等於 items 的總和。
5. "verification": 請辨識手寫的大寫金額 (handwritten_total_chinese) 與蓋章的店名 (stamp_shop_name) 用於後續驗證。
6. 若欄位無法辨識或不存在，請留空字串 "" 或 null。
```

### 3.3 錯誤處理 (Error Handling)

*   **API Failure**: 網路錯誤或 Quota Exceeded 時的 Fallback？
    *   *Option A*: Fail job immediately (User retry).
    *   *Option B*: Fallback to Local VLM (暫不考慮，簡化複雜度). -> **選 Option A**
*   **Content Safety**: Gemini 有時會因為 Safety Filter 拒絕回答。
    *   需設低 Safety Threshold (`BLOCK_NONE` or `BLOCK_ONLY_HIGH`).

---

## 4. 任務清單 (Task List)

- [ ] **Environment Setup**
    - [ ] Install `google-generativeai`
    - [ ] Add `GOOGLE_API_KEY` to `.env` or config
- [ ] **Refactor `vision_handler.py`**
    - [ ] Implement `GeminiClient` class or method
    - [ ] Update `process_handwritten` to use Gemini
    - [ ]Add retry logic for API calls
- [ ] **Verify**
    - [ ] Test with sample handwritten receipt
    - [ ] Verify JSON structure matches system requirements

---

## 5. 相容性確認 (Compatibility Check)

*   **ReceiptProcessor**: 不需要大幅修改，因為介面仍是 `vision_handler.process_handwritten(image)` -> returns `json`.
*   **Frontend**: 不需要修改，因為回傳的資料結構不變。
