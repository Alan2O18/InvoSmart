# v0.0.30 計畫：VLM 預算品類限制、取消預填內部 ID 與 QR 二次對帳啟用

本計畫旨在修正目前收據處理流程中的三個關鍵 Bug 與功能缺失，優化 AI 辨識的精準度與對帳機制的完整性。

---

## 1. 功能需求與修改設計

### A. VLM 預算支出品類限制 (VLM Category Constraint)
* **現狀問題**：目前 VLM 在辨識收據品項時會自行推想一個「品類 (Category)」（例如 "餐食"），但該品類可能根本沒有出現在使用者的專案預算表或報表中，導致導出時無法自動歸類或發生對齊混亂。
* **修改設計**：
  1. **專案預算品類注入**：在背景 Worker (`workers.py`) 呼叫 `receipt_processor.process(image)` 時，將 `project_id` 傳入。
  2. **動態 Prompt 限制**：在 `ReceiptProcessor` 中，藉由 `project_repo` 載入專案的 `metadata.budgetExpense`。提取出其中所有的唯一「項目名稱」作為限定的分類列表。
  3. **限制 VLM 輸出**：如果該專案已定義預算支出品類，將其作為 `prompt_context` 傳入 VLM，並在 prompt 中明確限制：
     * *「【限制】items 中每個品項的 category 欄位，必須只能從以下列表中選擇，絕對不可自行發明或推想其他品類：[品類列表]」*。

### B. 取消 VLM 預填內部 ID 與欄位獨立化 (Independent Voucher ID & Invoice ID)
* **現狀問題**：
  1. VLM 無法預測由使用者手動編排的「內部憑證編號 (`voucher_id`)」。但目前後端在 VLM 處理完畢後，若 `voucher_id` 為空，會自動將官方「發票號碼 (`invoice_id`)」複製填入 `voucher_id`。這導致使用者打開編輯器時，看到「內部憑證編號」欄位被強制預填了發票號碼，必須手動刪除或修改，十分不便。
  2. 後端 `_reconstruct_display_json` 存在嚴重設計 Bug，直接將 `header.invoice_id` 強制賦值為 `job.voucher_id`。這導致只要使用者儲存了自訂的內部編號（例如 V-001），發票本身的官方號碼（例如 AB12345678）在前端載入時就會被 `V-001` 覆蓋丟失，兩個欄位無法獨立並存。
* **修改設計**：
  1. **取消 Fallback 複製**：後端在 VLM 擷取資料後，不將 `invoice_id` 複製至 `voucher_id`。讓 `voucher_id` 預設保持為空字串，等待使用者人工編排或系統聯動生成。
  2. **獨立讀取與呈現**：修改 `job_repository.py` 的 `_reconstruct_display_json`，從原始 VLM/Manual JSON 中正確讀取 `invoice_id`，使其與 `voucher_id` 分離，不再相互覆蓋。

### C. 啟用 QR Code 二次對帳與驗證機制 (QR Secondary Reconciliation)
* **現狀問題**：
  1. 目前 QR Code 掃描後僅直接覆蓋 VLM 的部分欄位，沒有真正發揮「二次對帳（比對 VLM 與 QR 是否一致）」的作用。
  2. 後端 `python_validator.py` 存在評分 Bug，檢查的變數是不存在於 payload 頂層的 `qr_decode`，導致「來源可靠性 (15%)」評分從未被正確計入。
* **修改設計**：
  1. **保存 VLM 原始預測**：在 QR Code 覆蓋前，保留 VLM 辨識的原始 `invoice_id`、`date`、`total`。
  2. **對帳比對與 Bug 修復**：
     * 修改 `python_validator.py`，正確從 `verification.qr_verified` 檢查 QR 驗證狀態。
     * 若 QR Code 驗證成功，比對 VLM 的原始欄位與 QR Code 的數位解碼值。若兩者有不符（例如發票號碼 OCR 錯字、日期轉換錯誤、金額不同），則自動在 `validation.issues` 中加入明確的對帳警示資訊（例如 `[QR對帳] 發票號碼不符: VLM='AB1234567B', QR='AB12345678'`）。
  3. **前端狀態徽章 (Badge)**：修改 `JsonFieldEditor.vue`，在「驗證特徵」區塊中，若 `qr_verified` 為真，顯示亮綠色的 **「🟢 已通過 QR 數位驗證對帳」** 徽章；若有對帳問題，則在「邏輯驗證結果」中以紅字顯著列出對帳警示。

---

## 2. 檔案異動清單

### 後端處理與驗證
* **[MODIFY]** `backend/processing/receipt_processor.py`
  * 修改 `process` 方法，接收 `project_id`。
  * 若 `project_id` 存在，讀取專案預算品類並注入 RAG context / Prompt。
  * 在 QR 資料合併前，記錄對帳比對結果並寫入 verification。
* **[MODIFY]** `backend/engine/workers.py`
  * 在呼叫 `receipt_processor.process` 時傳入當前任務的 `project_id`。
* **[MODIFY]** `backend/repositories/job_repository.py`
  * 移除 `voucher_id` 在處理初始 VLM 結果時的強制 fallback 邏輯。
  * 修正 `_reconstruct_display_json`，使 `invoice_id` 與 `voucher_id` 的讀取各自獨立，避免互相覆蓋。
* **[MODIFY]** `backend/processing/python_validator.py`
  * 修正對 `qr_verified` 的判斷路徑，確保 QR 評分權重 (15%) 生效。
  * 若有對帳不符，將差異警示加入 `issues` 列表中。

### 前端介面
* **[MODIFY]** `frontend/src/components/JsonFieldEditor.vue`
  * 在驗證特徵區塊，新增 `qr_verified` 的動態狀態徽章 (Badge)，優化視覺反饋。
