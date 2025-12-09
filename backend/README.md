# Backend 後端模組說明

本文件說明後端專案的架構、各模組功能與職責劃分。

## 專案結構

```
backend/
├── main.py              # FastAPI 應用程式進入點
├── engine/              # 核心引擎層
├── managers/            # 專案與任務管理層
├── processing/          # 影像與文字處理層
├── routers/             # API 路由層
└── utils/               # 通用工具層
```

---

## 模組說明

### 1. Engine 核心引擎層 (`engine/`)

#### `core.py`
**核心引擎單例（Singleton）**

- **職責**：協調所有子系統，提供統一的專案生命週期管理介面
- **主要功能**：
  - 專案建立與初始化
  - OCR/LLM Worker 執行緒管理
  - TaskManager 單例管理
  - 發票分割、圖片操作統一入口
- **設計模式**：Singleton（單例模式）
- **主要方法**：
  - `create_project()` - 建立新專案
  - `run_ocr()` / `run_llm()` - 啟動批次處理
  - `run_single_ocr()` / `run_single_llm()` - 單一任務處理
  - `get_task_manager()` - 取得專案的 TaskManager 實例

#### `export.py`
**匯出處理器（ExportHandler）**

- **職責**：處理專案匯出、封存與人工修正流程
- **主要功能**：
  - Excel 匯出：將所有 Job 的 OCR/LLM 結果匯出成 Excel 檔案
  - 專案封存：打包專案為 ZIP 檔案，包含所有檔案和資料庫
  - 人工修正重新生成：從 Excel 的「人工修正」欄位重新生成結構化資料
- **主要方法**：
  - `archive_to_excel()` - 產生 Excel 報表
  - `seal_project()` - 封存專案為 ZIP
  - `regenerate_from_archive()` - 人工修正後重新生成

#### `file_ops.py`
**檔案操作處理器（FileOps）**

- **職責**：管理原始檔案、執行發票分割、圖片操作
- **主要功能**：
  - 發票分割：使用 ReceiptSplitter 分割原始圖片
  - 原始檔案管理：取得、新增原始圖片
  - 圖片操作：旋轉圖片
- **主要方法**：
  - `run_splitting()` - 批次分割發票
  - `get_raw_files()` - 取得原始檔案清單
  - `add_project_files()` - 新增檔案到專案
  - `rotate_image()` - 旋轉圖片

#### `workers.py`
**工作執行緒函數**

- **職責**：提供 OCR/LLM 的背景處理邏輯
- **主要功能**：
  - CPU Worker：從 TaskManager 取得待處理的 OCR 任務並執行
  - GPU Worker：從 TaskManager 取得待處理的 LLM 任務並執行
- **主要函數**：
  - `process_ocr_task()` - 處理單一 OCR 任務
  - `process_llm_task()` - 處理單一 LLM 任務
  - `start_cpu_worker()` - 啟動 OCR 工作迴圈
  - `start_gpu_worker()` - 啟動 LLM 工作迴圈

---

### 2. Managers 專案與任務管理層 (`managers/`)

#### `project_manager.py`
**專案管理器（ProjectManager）**

- **職責**：專案管理的外觀類別（Facade），整合 CRUD 和 Setup
- **設計模式**：Facade（外觀模式）
- **主要功能**：
  - 專案清單查詢
  - 專案設置與初始化
  - 專案狀態更新
  - 群組管理（用於多使用者場景）
- **主要方法**：
  - `setup_project()` - 設置新專案
  - `list_projects()` - 列出所有專案
  - `get_project_status()` - 取得專案狀態
  - `update_activity_info()` - 更新活動資訊

#### `project_crud.py`
**專案 CRUD 操作（ProjectCRUD）**

- **職責**：管理全域資料庫中的專案記錄
- **資料庫**：`projects.db` (SQLite)
- **主要資料表**：
  - `projects` - 專案資訊（project_id, name, status, metadata 等）
  - `groups` - 群組資訊（group_name, leader_name）
- **主要方法**：
  - `register_project()` - 註冊新專案
  - `list_projects()` - 查詢所有專案
  - `update_project_status()` - 更新專案狀態
  - `delete_project()` - 刪除專案記錄

#### `project_setup.py`
**專案初始化設置（ProjectSetup）**

- **職責**：建立專案目錄結構和初始化 jobs.db
- **主要功能**：
  - 建立專案資料夾（原始輸入、分割發票）
  - 初始化 jobs.db 資料庫
  - 複製輸入檔案到專案目錄
- **目錄結構**：
  ```
  workspace/{project_id}/
  ├── 原始輸入/
  ├── 分割發票/
  └── jobs.db
  ```
- **主要方法**：
  - `setup_project()` - 設置專案環境
  - `_init_jobs_db()` - 初始化 jobs 資料庫
  - `delete_project_files()` - 刪除專案檔案

#### `task_manager.py`
**任務佇列管理器（TaskManager）**

- **職責**：管理單一專案的所有 Job 的生命週期和狀態轉換
- **資料庫**：每個專案有獨立的 `jobs.db`
- **Job 狀態流程**：
  ```
  ready → pending → running → done
                    ↓
                  failed
  ```
- **主要功能**：
  - Job 入隊（enqueue）
  - 工作認領（claim_for_ocr / claim_for_llm）
  - 狀態更新（complete_ocr / complete_llm / fail_job）
  - Job 刪除與查詢
- **主要方法**：
  - `enqueue()` - 新增任務到佇列
  - `claim_for_ocr()` - 認領 OCR 任務
  - `claim_for_llm()` - 認領 LLM 任務
  - `complete_ocr()` - 完成 OCR 階段
  - `complete_llm()` - 完成 LLM 階段
  - `get_job_details()` - 取得 Job 詳細資訊
  - `save_manual_text()` - 儲存人工修正文字

---

### 3. Processing 影像與文字處理層 (`processing/`)

#### `ocr_handler.py`
**OCR 處理器（OCRHandler）**

- **職責**：使用 PaddleOCR 進行文字辨識和版面重建
- **主要功能**：
  - 執行 OCR 辨識，回傳文字與座標
  - 版面重建：根據座標重組文字排版
- **主要方法**：
  - `do_paddleocr()` - 執行 OCR，回傳結構化結果
  - `reconstruct_layout()` - 重建文字版面

#### `llm_handler.py`
**LLM 處理協調器（LLMHandler）**

- **職責**：整合文字校正和資料提取流程
- **主要功能**：
  - 協調 TextCorrector 和 DataExtractor
  - 提供統一的 LLM 處理介面
- **主要方法**：
  - `structure_with_llm()` - 完整處理流程（校正 + 提取）
  - `regenerate_from_corrected_text()` - 從人工修正文字重新提取資料

#### `text_corrector.py`
**文字校正器（TextCorrector）**

- **職責**：使用 LLM 校正 OCR 錯誤和簡繁轉換
- **主要功能**：
  - 修正視覺相似錯誤（如「每報紙」→「海報紙」）
  - 簡體轉繁體
  - 語意錯誤修正
- **主要方法**：
  - `correct_text()` - 校正文字

#### `data_extractor.py`
**資料提取器（DataExtractor）**

- **職責**：使用 LLM 從校正後文字提取結構化資料
- **輸出格式**：
  ```json
  {
    "supplier": "供應商名稱",
    "invoice_id": "發票號碼",
    "date": "YYYY-MM-DD",
    "items": [
      {"description": "品名", "quantity": 數量, "price": 價格}
    ],
    "total_amount": 總金額
  }
  ```
- **主要方法**：
  - `extract_data()` - 提取結構化資料

#### `receipt_splitter.py`
**發票分割器（ReceiptSplitter）**

- **職責**：使用 OpenCV 進行發票圖片偵測與分割
- **處理流程**：
  1. 灰階化 → 雙邊濾波
  2. Canny 邊緣檢測
  3. 形態學膨脹（連接斷裂邊緣）
  4. 輪廓搜尋與過濾（角度、長寬比、面積）
  5. 透視變換校正
- **主要方法**：
  - `split()` - 主要分割函數
  - `_validate_angles()` - 驗證四邊形角度
  - `_perspective_transform()` - 透視變換

---

### 4. Routers API 路由層 (`routers/`)

#### `projects.py`
**專案 REST API 端點**

- **職責**：提供所有專案操作的 HTTP 介面
- **主要端點類別**：
  - **專案 CRUD**：建立、列表、更新、刪除專案
  - **檔案操作**：上傳、旋轉、刪除原始檔案
  - **處理操作**：執行分割、OCR、LLM
  - **匯出操作**：匯出 Excel、封存專案
  - **Job 管理**：查詢、刪除 Job
  - **人工修正**：儲存修正文字、重新生成結果
  - **群組管理**：建立、查詢、刪除群組

#### `websocket.py`
**WebSocket 即時通訊端點**

- **職責**：即時推送 Job 狀態更新給前端
- **推送頻率**：每秒輪詢一次
- **推送資料**：
  - `jobs` - 所有 Job 的狀態清單
  - `progress` - 專案進度資訊

---

### 5. Utils 通用工具層 (`utils/`)

#### `parser.py`
**JSON 解析工具**

- **職責**：從 LLM 輸出提取結構化資料
- **主要功能**：
  - 解析 LLM 回傳的 JSON 字串
  - 正規化 items 欄位格式
  - 處理多種可能的 JSON 結構
- **主要函數**：
  - `extract_structured_data()` - 提取並正規化結構化資料

#### `utils.py`
**通用工具函數**

- **職責**：提供支援中文路徑的 OpenCV 讀寫功能
- **主要功能**：
  - 使用 `np.fromfile` 和 `tofile` 處理中文路徑
  - 避免 OpenCV 原生函數的路徑編碼問題
- **主要函數**：
  - `cv_imread_chinese()` - 讀取中文路徑圖片
  - `cv_imwrite_chinese()` - 寫入中文路徑圖片

---

## 資料流程

### 完整處理流程

```
1. 專案建立
   ↓
2. 上傳原始圖片
   ↓
3. 發票分割 (ReceiptSplitter)
   ↓
4. 任務入隊 (TaskManager.enqueue)
   ↓
5. OCR 處理 (OCRHandler)
   ↓
6. LLM 處理 (TextCorrector + DataExtractor)
   ↓
7. 結果儲存 (TaskManager.complete_llm)
   ↓
8. 匯出 Excel (ExportHandler)
   ↓
9. (選用) 人工修正 → 重新生成
```

### 人工修正流程

```
1. 從 Excel 讀取「人工修正」欄位
   ↓
2. 使用 DataExtractor.extract_data() 重新提取
   ↓
3. 更新 Job 的 llm_result_json
   ↓
4. 產生新的 Excel 報表
```

---

## 設計模式

| 模式 | 應用位置 | 說明 |
|-----|---------|-----|
| **Singleton** | `Engine` | 確保全域唯一的引擎實例 |
| **Facade** | `ProjectManager` | 簡化 CRUD 和 Setup 的複雜介面 |
| **Strategy** | Processing 層 | OCR/LLM/Splitter 可獨立替換 |
| **Observer** | WebSocket | 即時推送狀態變化 |

---

## 執行緒安全

- **TaskManager**：使用 `threading.Lock` 保護資料庫操作
- **Engine**：Singleton 初始化使用 `__new__` 確保執行緒安全
- **Worker 執行緒**：獨立執行，透過 TaskManager 同步狀態

---

## 資料庫設計

### 全域資料庫 (`projects.db`)

```sql
CREATE TABLE projects (
  project_id TEXT PRIMARY KEY,
  name TEXT,
  root_path TEXT,
  status TEXT,      -- NEW, INGESTED, SPLIT, PROCESSING, PROCESSED, ARCHIVED, SEALED
  created_at REAL,
  updated_at REAL,
  notes TEXT,
  metadata TEXT     -- JSON 格式
);

CREATE TABLE groups (
  group_name TEXT PRIMARY KEY,
  leader_name TEXT
);
```

### 專案資料庫 (`workspace/{project_id}/jobs.db`)

```sql
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  image_path TEXT NOT NULL,
  status TEXT NOT NULL,        -- ready, pending, running, done, failed
  stage TEXT NOT NULL,          -- ocr, llm
  ocr_start_at REAL,
  ocr_done_at REAL,
  llm_start_at REAL,
  llm_done_at REAL,
  ocr_result_json TEXT,
  llm_result_json TEXT,
  manual_text TEXT,             -- 人工修正的 OCR 文字
  created_at REAL,
  updated_at REAL,
  auto_advance INTEGER DEFAULT 1
);

CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id TEXT,
  event_type TEXT,
  ts REAL,
  payload TEXT
);
```

---

## 依賴管理

### 核心依賴
- **FastAPI** - Web 框架
- **PaddleOCR** - OCR 引擎
- **Ollama** - LLM 處理
- **OpenCV (cv2)** - 影像處理
- **SQLite3** - 資料庫

### 測試依賴
- **pytest** - 測試框架
- **unittest.mock** - Mock 工具

---

## 未來改進方向

1. **效能優化**
   - 引入 Redis 做為 TaskManager 的佇列後端
   - 使用非同步 I/O (async/await) 處理檔案操作

2. **可靠性**
   - Job 失敗重試機制
   - 長時間停滯任務的自動標記

3. **可擴展性**
   - 支援多 Worker 節點（分散式處理）
   - 插件化的 OCR/LLM 引擎選擇

4. **可維護性**
   - 將大型檔案拆分（如 task_manager.py 454 行）
   - 增加單元測試覆蓋率至 80% 以上
