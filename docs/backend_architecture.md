# Backend 架構分析報告

> **文檔版本**: 2026-01-05
> **目的**: 提供完整的後端架構分析，幫助開發者理解各模組功能與修改程式

## 目錄結構總覽

```
backend/
├── main.py                 # FastAPI 應用程式入口
├── engine/                 # 核心業務邏輯層
│   ├── core.py            # Engine 單例 - 系統核心協調器
│   ├── workers.py         # Unified/Legacy Worker 背景處理
│   ├── file_ops.py        # 檔案操作（分割、上傳、旋轉）
│   └── export.py          # 匯出功能 Facade
├── managers/              # 專案與任務管理層
│   ├── task_manager.py    # TaskManager Facade
│   ├── job_repository.py  # Job 資料存取層 (SQLite)
│   ├── job_state_machine.py # Job 狀態機邏輯
│   ├── project_manager.py # ProjectManager Facade
│   ├── project_crud.py    # 專案 CRUD 操作
│   └── project_setup.py   # 專案初始化設定
├── processing/            # 影像與文字處理層
│   ├── receipt_processor.py # ReceiptProcessorV2 (主要流水線)
│   ├── rapidocr_handler.py  # RapidOCR (ONNX) 處理器
│   ├── vision_handler.py    # Qwen VLM 視覺處理器
│   ├── audit_handler.py     # 稽核與交叉驗證
│   ├── llm_handler.py       # LLM 文字校正與資料擷取
│   ├── prompts_config.py    # LLM Prompt 配置 (fstring)
│   ├── qr_handler.py        # QR Code 解碼與解析
│   ├── keyword_classifier.py # 收據分類器
│   ├── python_validator.py   # Python 資料驗算
│   └── receipt_splitter.py   # 發票分割 Facade
├── routers/               # API 路由層
│   ├── projects.py        # 專案相關 API
│   ├── files.py           # 檔案操作 API
│   ├── processing.py      # OCR/LLM 處理 API
│   ├── jobs.py            # Job 查詢 API
│   ├── correction.py      # 人工修正 API
│   └── groups.py          # 群組管理 API
└── utils/                 # 工具函數
    └── logger.py          # 日誌配置
```

---

## 1. Engine 層（核心業務邏輯）

### 1.1 core.py - Engine 單例

**設計模式**: Singleton + Facade

**職責**:
- 系統核心協調器，管理所有子系統
- 提供統一的 API 給 routers 調用
- 管理 Shared Queue 與 Worker Loop

**關鍵屬性**:
```python
class Engine:
    _instance = None  # 單例實例
    
    # 核心組件
    self.ocr_handler      # RapidOCRHandler / OCRHandler
    self.llm_handler      # LLMHandler
    self.receipt_processor # ReceiptProcessorV2
    self.project_manager  # ProjectManager
    
    # 全局佇列 (Global Worker Mode)
    self.ocr_queue        # OCR 任務佇列
    self.llm_queue        # LLM 任務佇列
    self.unified_queue    # 統一處理佇列 (推薦)
```

### 1.2 workers.py - Global Worker Loop

**架構變更**: 2025-12 改為 Global Worker 架構，取代了每個專案單獨的 Worker 線程。

**優勢**:
- 減少 context switching 開銷
- 避免大量線程競爭資源
- 統一的任務調度與優先級管理

#### `global_receipt_worker_loop(engine)` (Unified Mode)
```python
while True:
    # 1. 從統一佇列獲取任務
    task = engine.unified_queue.get()
    
    # 2. 獲取對應專案的 TaskManager
    tm = engine.get_task_manager(task.project_id)
    
    # 3. 執行完整處理流水線
    try:
        # OCR -> 分類 ->(電子/手寫/其他) -> 驗算 -> 自動修正
        result = engine.receipt_processor.process(image)
        tm.complete_job(task.job_id, result)
    except Exception as e:
        tm.fail_job(task.job_id, str(e))
```

#### `global_ocr_worker_loop` & `global_llm_worker_loop` (Legacy Mode)
- 僅在 `config.use_unified_worker = false` 時啟用
- 分別處理 OCR 和 LLM 佇列
- 舊有的兩階段處理邏輯

---

### 1.3 任務調度流程

```mermaid
sequenceDiagram
    participant F as 前端
    participant E as Engine
    participant Q as GlobalQueue
    participant W as GlobalWorker
    
    F->>E: run_ocr(project_id) (或 run_all)
    E->>Q: Enqueue All Ready Jobs
    E-->>F: {status: queued, count: N}
    
    loop Worker Loop
        W->>Q: get_task()
        Q-->>W: task
        W->>W: ReceiptProcessor.process()
        W->>DB: update_job_status(done)
    end
    
    F->>DB: Polling status
```

---

## 2. Managers 層（專案與任務管理）

### 2.1 TaskManager - Facade 模式

**設計模式**: Facade

**職責**: 整合 JobRepository 和 JobStateMachine 的功能

**組成**:
```python
class TaskManager:
    self._repository     # JobRepository - 資料存取
    self._state_machine  # JobStateMachine - 狀態轉換
    self.lock            # threading.Lock() - 線程安全
```

**關鍵方法分類**:

| 類別 | 方法 | 說明 |
|------|------|------|
| 佇列操作 | `enqueue()` | 新增 Job |
| | `claim_for_ocr()` | 獲取 OCR 任務 |
| | `claim_for_llm()` | 獲取 LLM 任務 |
| 狀態更新 | `complete_ocr()` | 完成 OCR |
| | `complete_llm()` | 完成 LLM |
| | `fail_job()` | 標記失敗 |
| 查詢 | `get_job()` | 取得單一 Job |
| | `list_jobs()` | 列出所有 Jobs |
| | `count_jobs()` | 統計 Jobs |

---

### 2.2 JobStateMachine - 狀態機

**職責**: 管理 Job 的狀態轉換邏輯

**狀態流程**:
```mermaid
stateDiagram-v2
    [*] --> ready : enqueue
    ready --> pending : mark_as_pending
    pending --> running : claim
    running --> done : complete
    running --> failed : fail
    done --> pending : reset_and_claim
    failed --> pending : reset_and_claim
```

**狀態定義**:
| 狀態 | 說明 |
|------|------|
| `ready` | 初始狀態，等待處理 |
| `pending` | 已排入佇列，等待 Worker |
| `running` | Worker 正在處理 |
| `done` | 處理完成 |
| `failed` | 處理失敗 |

**階段 (stage)**:
- `ocr`: OCR 處理階段
- `llm`: LLM 處理階段

---

### 2.3 JobRepository - 資料存取層

**職責**: 所有 SQLite CRUD 操作

**資料庫**: `{project_dir}/jobs.db`

**Jobs 表結構**:
```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    image_path TEXT,
    status TEXT,           -- ready/pending/running/done/failed
    stage TEXT,            -- ocr/llm
    ocr_result_json TEXT,  -- OCR 結果 JSON
    llm_result_json TEXT,  -- LLM 結果 JSON
    manual_ocr_text TEXT,  -- 人工修正文字
    created_at INTEGER,
    updated_at INTEGER,
    ocr_start_at INTEGER,
    ocr_done_at INTEGER,
    llm_start_at INTEGER,
    llm_done_at INTEGER,
    ...
);
```

---

## 3. Processing 層（影像與文字處理）

### 3.1 RapidOCR Handler

**主要 OCR 處理器**，使用 ONNX Runtime 執行推論。

| 方法 | 說明 |
|------|------|
| `do_ocr()` | 執行 OCR，返回結構化結果與統計 |
| `to_plain_text()` | 重組版面為純文字 |
| `get_high_confidence_text()` | 過濾低信心度結果 |
| `extract_numbers()` | 提取數字資訊 |

---

### 3.2 LLMHandler - LLM 處理器

**職責**: 使用 Ollama LLM 進行文字校正和資料擷取

**處理流程**:
```
input (OCR 文字)
    ↓
_correct_text()     ← 修正 OCR 錯誤、簡繁轉換
    ↓
_extract_data()     ← 提取結構化資料 (JSON)
    ↓
output {
    corrected_full_text: "...",
    structured_data: { supplier, invoice_id, items, ... }
}
```

**依賴**: Ollama 服務必須運行

---

### 3.3 ReceiptSplitter - 發票分割

**設計模式**: Facade

**子模組**:
- `ImagePreprocessor`: 灰階、濾波、Canny 邊緣檢測
- `ContourValidator`: 輪廓面積、形狀驗證
- `PerspectiveTransformer`: 透視變換校正

---

## 4. Routers 層（API 路由）

### 4.1 路由總覽

| 路由檔案 | 路徑前綴 | 說明 |
|---------|---------|------|
| `projects.py` | `/api/projects` | 專案 CRUD |
| `files.py` | `/api/projects/{id}/...` | 檔案操作 |
| `processing.py` | `/api/projects/{id}/...` | OCR/LLM 觸發 |
| `jobs.py` | `/api/projects/{id}/jobs` | Job 查詢 |
| `correction.py` | `/api/projects/{id}/jobs/{job_id}` | 人工修正 |
| `groups.py` | `/api/groups` | 群組管理 |

### 4.2 關鍵 API

```
POST /api/projects/{id}/split           → 分割發票
POST /api/projects/{id}/ocr             → 批次 OCR
POST /api/projects/{id}/llm             → 批次 LLM
POST /api/projects/{id}/jobs/{job_id}/ocr   → 單一 OCR
POST /api/projects/{id}/jobs/{job_id}/llm   → 單一 LLM
GET  /api/projects/{id}/jobs            → 列出 Jobs
```

---

## 5. 已知問題與待修復項目

### 5.1 Single OCR Worker 問題

> [!CAUTION]
> **問題描述**: 按下單一 OCR 按鈕後，前端沒有顯示狀態變化，後端日誌也沒有執行記錄。

**可能原因**:
1. `run_single_ocr` 中的 `tm._repository.update_job()` 可能沒有正確更新狀態
2. Worker 線程可能沒有正確啟動
3. `claim_for_ocr()` 可能因為狀態不符而無法獲取任務

**建議檢查點**:
```python
# core.py - run_single_ocr
with tm.lock:
    job = tm.get_job(job_id)  # ← 確認 job 存在
    tm._repository.update_job(...)  # ← 確認更新成功
    
# 確保啟動 Worker
thread_name = f"ocr-{project_id}"
if not any(t.name == thread_name ...):
    # ← 這裡應該啟動 worker
```

### 5.2 PaddleOCR 線程安全

目前解決方案：使用 `ocr_worker_lock` 全局鎖

但需確保：
1. 所有調用 `start_cpu_worker` 的地方都傳遞了這個鎖
2. 鎖不會導致死鎖

---

## 6. 修改指南

### 6.1 新增 OCR 引擎

1. 在 `processing/` 創建新的 handler 類
2. 實作 `process_receipt(image_array)` 方法
3. 在 `core.py` 的 `__init__` 中添加條件判斷
4. 更新 `config.json` 配置

### 6.2 新增 Job 狀態

1. 修改 `job_state_machine.py` 添加新的狀態轉換
2. 必要時修改 `job_repository.py` 的資料庫 schema
3. 更新前端對應的狀態顯示

### 6.3 新增 API

1. 在 `routers/` 中新增或修改路由檔案
2. 從 Engine 調用相應的方法
3. 在 `routers/__init__.py` 中 include 新路由

---

## 7. 測試建議

### 7.1 單元測試

```bash
cd backend
pytest tests/ -v
```

### 7.2 手動測試 OCR 流程

```python
# 直接測試 RapidOCR handler
from backend.processing.rapidocr_handler import RapidOCRHandler
import cv2

handler = RapidOCRHandler({})
image = cv2.imread("path/to/image.png")
result, stats = handler.do_ocr(image)
text = handler.to_plain_text(result)
print(text)
```

### 7.3 驗證 Worker 執行

在 `workers.py` 中添加日誌：
```python
def start_cpu_worker(...):
    logger.info(f"[CPU Worker] 開始運行: {project_id}")  # ← 確認看到這行
```

---

## 附錄：配置檔案說明

### config.json

```json
{
  "project_manager_settings": {
    "global_db_path": "~/.ai_agent_lab/global_projects.db",
    "workspace_root": "~/.ai_agent_lab/projects"
  },
  "ocr_settings": {
    "engine": "ppstructure",  // "basic" 或 "ppstructure"
    "language": "chinese_cht",
    "use_angle_cls": true
  },
  "llm_settings": {
    "model_name": "qwen3:1.7b"
  },
  "text_processing": {
    "opencc_config": "s2twp"  // 簡體轉繁體(台灣)
  }
}
```
