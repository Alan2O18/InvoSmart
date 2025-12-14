# 架構重構建議書

> **日期**: 2024-12-14
> **主題**: 後端 Worker 架構優化方案比較與建議

## 1. 問題背景
目前的後端架構採用「每個專案獨立 Worker」的模式，但因為核心依賴（PaddleOCR）並非線程安全，我們被迫引入了「全局鎖（Global Lock）」來強制序列化執行。這導致了架構設計與實際執行模型的不匹配：
- **名義上**：並行多線程（多個 Worker 同時存在）
- **實際上**：序列單線程（所有 Worker 搶同一把鎖）

這增加了上下文切換的開銷，且讓程式碼邏輯變得複雜（需要在多處傳遞鎖、管理多個線程生命週期），卻沒有帶來並行的效能紅利。

---

## 2. 方案比較

用戶提出了兩個主要方案，以下是詳細分析：

### 方案一：全局 Worker (Global Worker)
> 開局就開兩個每秒檢測 queue 的線程跑 OCR 還有 LLM

* **架構**：
  * Server 啟動時創建 1 個 OCR 線程和 1 個 LLM 線程（常駐）。
  * 一個全局的 `TaskQueue` 用於存放待處理任務。
  * 所有 API 請求只負責將任務丟入 Queue。

* **優點**：
  * **完全符合 PaddleOCR 限制**：既然只能序列執行，就只開一個線程，完全不需要鎖。
  * **極度簡單的生命週期**：Worker 與 Server 同生共死，不用擔心 Worker 意外退出或殭屍線程。
  * **資源可控**：明確知道只有 2 個背景線程在消耗資源。
  * **除錯容易**：出問題時只需看這唯一的線程在做什麼。

* **缺點**：
  * 需要實作跨專案的任務調度（Global Queue）。
  * 若使用全新的 Global DB 會增加資料同步複雜度。

### 方案二：按需啟動 Worker (On-demand Worker) - 當前模式
> 在每次有新的 TM 創建去檢查與啟動新 worker 來跑

* **架構**：
  * 每個專案有自己的 Worker 線程。
  * 使用全局鎖來防止衝突。

* **優點**：
  * 資料隔離好，專案之間互不影響（除了搶鎖時）。
  * 更容易實作「暫停特定專案」的功能。

* **缺點**：
  * **假並行**：開了 10 個線程卻有 9 個在等鎖，浪費系統資源。
  * **死鎖風險**：鎖的粒度如果控制不好（例如在持有鎖時進行 IO），容易卡死整個系統。
  * **管理複雜**：Engine 需要追蹤所有動態產生的線程，確保它們正確關閉。

---

## 3. 最終建議：方案一的改良版（In-Memory Hybrid Queue）

我強烈建議採用 **方案一 (Global Worker)**，這是最簡單、最穩健且效能最好的設計。

為了避免「引入新 DB」帶來的複雜度，我建議採用 **In-Memory Queue + Existing DBs** 的混合模式：

### 3.1 核心設計
1. **Engine** 啟動時建立兩個 Python 原生 `queue.Queue`：`ocr_queue` 和 `llm_queue`。
2. **Engine** 啟動 2 個常駐 Consumer 線程：
   - `GlobalOCRWorker`: 監聽 `ocr_queue`
   - `GlobalLLMWorker`: 監聽 `llm_queue`
3. **TaskManager** 不再負責啟動 Worker，只負責：
   - 更新 Job 狀態為 `pending` (寫入各自的 DB)。
   - 將 `(project_id, job_id)` Tuple 推送至全局 Queue。

### 3.2 運作流程
```python
# API 觸發
def run_single_ocr(project_id, job_id):
    tm = get_tm(project_id)
    tm.mark_pending(job_id)     # 寫入 DB (持久化)
    engine.ocr_queue.put((project_id, job_id)) # 推送至內存佇列 (調度)

# Global Worker
def global_ocr_loop():
    while True:
        project_id, job_id = engine.ocr_queue.get()
        tm = engine.get_task_manager(project_id)
        
        # 再次檢查狀態 (防止在排隊時被刪除或取消)
        job = tm.get_job(job_id)
        if job.status == 'pending':
             # 處理任務 (不需要鎖！因為我是唯一的 OCR 線程)
             tm.set_running(job_id)
             process_ocr(job)
             tm.set_done(job_id)
             
             # 自動觸發 LLM (Pipeline)
             engine.llm_queue.put((project_id, job_id))
```

### 3.3 崩潰恢復 (Crash Recovery)
如果 Server 崩潰，內存 Queue 會消失，但 DB 狀態還在。
**解決方案**：
在 `Engine` 啟動時（`__init__`），掃描所有 Active Projects 的 DB，找出狀態為 `pending` 或 `running` 的 Job，將它們重新加入 Queue。

### 3.4 總結優勢
1. **移除全域鎖**：代碼中不再需要任何 `with lock:`，死鎖風險降為 0。
2. **邏輯清晰**：`Producer` (API) 與 `Consumer` (Worker) 職責完全分離。
3. **無縫兼容**：不需要改變現有的 DB 結構，只需要改變調度邏輯。

這將極大程度簡化您的程式碼，讓下一個維護者能輕易理解系統運作原理。
