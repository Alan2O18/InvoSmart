# 資料庫集中化與 AI 建議模式計畫 (DB Centralization & AI Suggestion Plan)

## 1. 現狀架構與問題分析 (Current Architecture & Issues)
目前系統的資料儲存有分散的情形：
- **`global.db`**: 儲存全域的 `projects`、`groups`、`vocabulary` (詞彙) 以及 `suggestions` (建議詞)。
- **各專案 `jobs.db`**: 每個專案資料夾底下都有一個獨立的 `jobs.db`，儲存該專案的 `jobs` (發票/單據辨識任務) 與 `events`。

**產生的問題：**
1. **資料不互通**：跨專案的資料分析與查詢非常困難，無法輕易取得歷史所有已驗證的單據結果。
2. **AI 無法汲取全局經驗**：每次建立新專案時，新的 `jobs.db` 為空，難以讓 AI 模型參考過往人工修正 (manual_json) 的結果。
3. **建議詞邏輯重複**：目前的程式碼既有 `ProjectRepository` 內的 `vocabulary`，又有 `SuggestionRepository` 的 `suggestions`。

---

## 2. 集中化目標 (Centralization Goals)
將所有的 `jobs.db` 以及 `global.db` 合併為一個**單一集中的資料庫 (Centralized Database)**，並建立回饋循環 (Feedback Loop)，將人工校正後的正確資料整理成「建議詞庫」，同時提供給「前端使用者介面」與「AI 辨識引擎」。

---

## 3. 實作計畫 (Implementation Plan)

為確保系統穩定過渡，資料庫整合將分為下列兩步進行：

### 第一步：整合品項與建議詞資料 (優先提升 AI 辨識)
1. **統一 Suggestions 表格與資料遷移**：在目前的 `global.db` 中，合併 `ProjectRepository` 的 `vocabulary` 與 `SuggestionRepository` 的 `suggestions`。
   - 撰寫一次性遷移腳本，將既有 `vocabulary` 表中的紀錄匯入統一的 `suggestions` 表，完成後棄用舊表。
   - **權重設計**：保留 `count` (頻率) 欄位，並加上 `last_used_at` 欄位。AI 將優先參考「最近常用」且「高頻」的詞彙。
   - **標籤分類嚴謹化**：明確定義 `category` 標籤 (例如 `item_name`, `supplier_name`)，避免 AI 混淆欄位屬性。
2. **AI 動態 Prompt 整合 (RAG)**：在呼叫 VLM 進行辨識前，從全域建議詞庫抓取最高頻的前 N 筆買方、賣方與常見品項清單放入 System Prompt。
   - **幻覺預防**：在 Prompt 中明確限制：「*如果清單中沒有相似項，請依照原始圖片辨識，不要強行湊合*」。
3. **建立回饋機制**：使用者手動更正辨識結果並儲存時，自動寫入並更新全域建議詞庫。

### 第二步：全面整合資料庫 (直接取代舊有設計)
1. **完整 Schema 落地**：在 `global.db` 建立包含所有細節的 `jobs` 與 `events` 表，並以 `project_id` 區隔。確保資料庫連線開啟 `PRAGMA journal_mode=WAL;` 處理高併發寫入。
2. **執行 Migration**：撰寫 Python 腳本走訪所有專案的 `jobs.db`，將所有 Json 辨識結果與歷史紀錄全部遷移至 `global.db`。
3. **廢除分散式檔案庫與備份機制**：全面修改 `JobRepository` 指向單一主資料庫 (`global.db`)，摒棄原本向各專案目錄寫入的邏輯。
4. **回退計畫與資料保護**：在刪除各專案目錄下的 `jobs.db` 前，由 Migration 腳本自動將其更名備份為 `{project_root}/jobs.db.bak`，保留一個版本週期後再做最終清除。
5. **全域查詢介面**：實作全域查詢層，讓系統能有效列出所有專案的任務概況與進度。

---

## 4. 預期效益
- **對開發與維護**：所有資料集中一處，方便資料庫備份、Migration、關聯查詢以及未來轉移至 Cloud DB。
- **對使用者**：表單輸入/編輯時，自動完成 (Autocomplete) 能帶出全公司跨專案的歷史資料。
- **對 AI 引擎**：具備歷史記憶，對經常往來的廠商與獨特品項的辨識正確率將顯著提升，減少幻覺。預期完成第一步後，常見廠商與品項的**辨識正確率從現有的情況提升至 90% 以上**（可透過 A/B 測試量化改善幅度）。

---

## 5. 常見架構與效能疑慮 (Architecture Q&A)

### Q1: 現有的資料庫設計 (jobs.db) 如果直接餵給 AI，能讓 AI 有效學習使用者的修正嗎？
**A1: 不能。如果直接將整張發票的完整 JSON (包含大量無意義坐標與雜訊) 餵給 AI，反而會讓 AI 迷失重點並過度消耗 Token。**
* **解決方案**：第一步的重點在於**「知識萃取」**。系統只會將使用者確認過的高頻精華（如：正確的買賣方統編、名稱、商品品項）寫入統一的建議詞庫 (`global.db` 的 `suggestions`)。當下一張發票辨識時，只將這份精確的簡短清單透過 RAG (動態 Prompt) 提供給 AI 參考，確保 AI 能在極低 Token 消耗下精準參照過往經驗。

### Q2: 將所有專案資料集中到寫入單一資料庫 (`global.db`)，讀寫速度跟得上嗎？
**A2: 以目前的規模，SQLite 絕對跟得上，但需要開啟特定的設定。**
* SQLite 的讀取速度極快，瓶頸主要在於「併發寫入 (Concurrent Writes)」。
* **解決方案**：在實作第三步完整遷移時，在資料庫連線中強制開啟 **Write-Ahead Logging (`PRAGMA journal_mode=WAL;`)**。這能讓 SQLite 達到毫秒級的並發讀寫效能，足以應付數十個背景 Worker 同時處理發票的場景。若未來業務量增長至每秒上百筆寫入，再評估直接無痛轉移至 PostgreSQL。

### Q3: 線程安全 (Thread Safety) 對於這次重構重要嗎？
**A3: 這是從「分散式 `jobs.db`」改為「集中式 `global.db`」時最關鍵的工程細節。**
* 過去每個專案獨立寫入各自的檔案，幾乎沒有衝突風險。集中之後，所有任務都在競爭同一個 `global.db` 檔案鎖。
* **解決方案**：
    1. 在 `sqlite3.connect` 中明確加入 `check_same_thread=False` 與適當的 `timeout`。
    2. 在所有的 Repository 寫入操作 (特別是 `update_job` 等高頻更新) 必須加上 Python `threading.Lock()` 在應用層級進行排隊鎖控，避免系統拋出 `database is locked` 的錯誤。
