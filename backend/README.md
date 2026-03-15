# Backend 後端模組說明

本文件說明後端專案的架構、各模組功能與職責劃分。

> **最後更新**：2025-12-09（活動術語重構與自動狀態同步功能完成後）

## 專案結構

```
backend/
├── main.py              # FastAPI 應用程式進入點
├── engine/              # 核心引擎層
│   ├── core.py          # 引擎單例
│   ├── export.py        # 匯出 Facade
│   ├── excel_exporter.py    # Excel 匯出
│   ├── archive_handler.py   # 專案封存
│   ├── regeneration_handler.py  # 人工修正重新生成
│   ├── file_ops.py      # 檔案操作
│   └── workers.py       # 工作執行緒
├── managers/            # 專案與任務管理層
│   ├── project_manager.py   # 專案管理 Facade
│   ├── project_crud.py      # 專案 CRUD
│   ├── project_setup.py     # 專案初始化
│   ├── task_manager.py      # 任務管理 Facade
│   ├── job_repository.py    # Job 資料存取層
│   └── job_state_machine.py # Job 狀態機邏輯
├── processing/          # 影像與文字處理層
│   ├── ocr_handler.py       # OCR 處理器
│   ├── llm_handler.py       # LLM 處理器 (含校正與提取)
│   ├── receipt_splitter.py  # 發票分割 Facade
│   ├── image_preprocessor.py    # 影像預處理
│   ├── contour_validator.py     # 輪廓驗證
│   └── perspective_transform.py # 透視變換
├── routers/             # API 路由層
│   ├── __init__.py      # 路由匯總
│   ├── projects.py      # 專案 CRUD 端點
│   ├── files.py         # 檔案操作端點
│   ├── processing.py    # 處理操作端點
│   ├── jobs.py          # Job 管理端點
│   ├── correction.py    # 人工修正端點
│   ├── groups.py        # 群組管理端點
│   └── websocket.py     # WebSocket 端點
└── utils/               # 通用工具層
    ├── parser.py        # JSON 解析
    └── utils.py         # 通用工具
```

---

## 模組說明

### 1. Engine 核心引擎層 (`engine/`)

#### `core.py` - 核心引擎單例
- **設計模式**：Singleton
- **職責**：協調所有子系統，提供統一的專案生命週期管理介面
- **主要方法**：`create_project()`, `run_ocr()`, `run_llm()`, `get_task_manager()`

#### `export.py` - 匯出 Facade
- **設計模式**：Facade
- **職責**：整合 Excel 匯出、封存和人工修正功能
- **委派至**：`ExcelExporter`, `ArchiveHandler`, `RegenerationHandler`

#### `excel_exporter.py` - Excel 匯出
- **職責**：將 Job 結果匯出為 Excel 檔案
- **主要方法**：`archive_to_excel()`, `run_excel()`

#### `archive_handler.py` - 專案封存
- **職責**：打包專案為 7z/ZIP 檔案
- **主要方法**：`seal_project()`

#### `regeneration_handler.py` - 人工修正重新生成
- **職責**：從 Excel 的「人工修正」欄位重新生成結構化資料
- **主要方法**：`regenerate_from_archive()`

#### `file_ops.py` - 檔案操作
- **職責**：管理原始檔案、發票分割、圖片操作

#### `workers.py` - 工作執行緒
- **職責**：OCR/LLM 背景處理邏輯

---

### 2. Managers 專案與任務管理層 (`managers/`)

#### `project_manager.py` - 專案管理 Facade
- **設計模式**：Facade
- **職責**：整合 CRUD 和 Setup 功能
- **新功能**：
  - `sync_status_to_db()` - 自動計算並同步活動狀態到資料庫
  - 狀態檢測包含 `pending`, `running`, `processing` 狀態

#### `project_crud.py` - 專案 CRUD
- **資料庫**：`global_projects.db`
- **職責**：管理全域專案記錄
- **活動欄位**：
  - `project_id` - 活動 ID（主鍵）
  - `name` - 活動名稱（前端顯示用）
  - `status` - 活動狀態（自動同步）
  - `metadata` - JSON 格式的額外資訊

#### `project_setup.py` - 專案初始化
- **職責**：建立專案目錄和 jobs.db

#### `task_manager.py` - 任務管理 Facade
- **設計模式**：Facade
- **職責**：整合 JobRepository 和 JobStateMachine
- **委派至**：`JobRepository`, `JobStateMachine`

#### `job_repository.py` - Job 資料存取層
- **職責**：所有 SQLite CRUD 操作和事件記錄
- **主要方法**：
  - `insert_job()`, `get_job()`, `delete_job()`
  - `list_jobs()`, `count_jobs()`
  - `emit_event()`

#### `job_state_machine.py` - Job 狀態機邏輯
- **職責**：Job 狀態轉換和工作流程邏輯
- **狀態流程**：
  ```
  ready → running → done
           ↓
         failed
  ```
- **主要方法**：
  - `claim_for_ocr()`, `claim_for_llm()`
  - `complete_ocr()`, `complete_llm()`
  - `fail_job()`, `reset_and_claim()`

---

### 3. Processing 影像與文字處理層 (`processing/`)

#### `ocr_handler.py` - OCR 處理器
- **職責**：使用 PaddleOCR 進行文字辨識和版面重建

#### `llm_handler.py` - LLM 處理器
- **職責**：整合文字校正 (`_correct_text`) 和資料提取 (`_extract_data`)
- **主要方法**：
  - `structure_with_llm()` - 完整處理流程
  - `regenerate_from_corrected_text()` - 人工修正重新提取

#### `receipt_splitter.py` - 發票分割 Facade
- **設計模式**：Facade
- **職責**：整合預處理、驗證和變換功能
- **委派至**：`ImagePreprocessor`, `ContourValidator`, `PerspectiveTransformer`

#### `image_preprocessor.py` - 影像預處理
- **職責**：灰階轉換、濾波、Canny 邊緣檢測、形態學運算
- **主要方法**：`preprocess()`, `find_contours()`

#### `contour_validator.py` - 輪廓驗證
- **職責**：驗證輪廓的幾何屬性（角度、長寬比）
- **主要方法**：
  - `order_points()` - 頂點排序
  - `validate_angles()` - 角度驗證
  - `validate_aspect_ratio()` - 長寬比驗證

#### `perspective_transform.py` - 透視變換
- **職責**：執行透視校正和去背處理
- **主要方法**：`transform()`

---

### 4. Routers API 路由層 (`routers/`)

路由現已按功能拆分為獨立模組：

| 模組 | 端點數 | 職責 |
|-----|-------|------|
| `projects.py` | 5 | 活動 CRUD（含自動狀態同步） |
| `files.py` | 4 | 檔案操作（上傳、旋轉、刪除） |
| `processing.py` | 7 | 處理操作（split、OCR、LLM、export） |
| `jobs.py` | 5 | Job 管理（查詢時自動同步狀態） |
| `correction.py` | 2 | 人工修正（儲存、重新生成） |
| `groups.py` | 3 | 群組管理 |
| `websocket.py` | 1 | WebSocket 即時推送 |

#### `__init__.py` - 路由匯總
```python
router = APIRouter()
router.include_router(projects.router)
router.include_router(files.router)
router.include_router(processing.router)
router.include_router(jobs.router)
router.include_router(correction.router)
router.include_router(groups.router)
```

---

### 5. Utils 通用工具層 (`utils/`)

#### `parser.py` - JSON 解析工具
- **職責**：從 LLM 輸出提取結構化資料

#### `utils.py` - 通用工具函數
- **職責**：支援中文路徑的 OpenCV 讀寫

---

## 設計模式

| 模式 | 應用位置 | 說明 |
|-----|---------|------|
| **Singleton** | `Engine` | 全域唯一引擎實例 |
| **Facade** | `ProjectManager`, `TaskManager`, `ExportHandler`, `ReceiptSplitter` | 簡化複雜子系統介面 |
| **Repository** | `JobRepository` | 資料存取層抽象 |
| **State Machine** | `JobStateMachine` | Job 狀態轉換邏輯 |
| **Strategy** | Processing 層 | OCR/LLM/Splitter 可獨立替換 |
| **Observer** | WebSocket | 即時推送狀態變化 |

---

## 資料流程

### 完整處理流程

```
1. 專案建立 → 2. 上傳原始圖片 → 3. 發票分割
                                    ↓
4. 任務入隊 → 5. OCR 處理 → 6. LLM 處理
                              ↓
7. 結果儲存 → 8. 匯出 Excel → 9. (選用) 人工修正
```

---

## 測試

- **測試框架**：pytest
- **測試數量**：89 個測試案例
- **執行命令**：`pytest tests/ -v`

---

## 重構歷史

### 2025-12-09 重構

| 原始檔案 | 行數 | 拆分結果 |
|---------|-----|---------|
| `routers/projects.py` | 338 | → 6 個路由模組 |
| `engine/export.py` | 388 | → 4 個匯出模組 |
| `managers/task_manager.py` | 454 | → 3 個管理模組 |
| `processing/receipt_splitter.py` | 415 | → 4 個處理模組 |

所有重構使用 **Facade 模式** 保持向後相容性。

### 2025-12-09 活動術語重構與自動狀態同步

**術語統一**：
- 前端全面改用「活動」（Activity）術語
- 資料庫使用 `name` 欄位儲存活動名稱
- `project_id` 作為活動 ID（主鍵）

**自動狀態同步**：
- 新增 `ProjectManager.sync_status_to_db()` 方法
- `GET /api/projects/{id}` 自動同步狀態
- `GET /api/projects/{id}/jobs` 自動同步狀態
- 狀態根據檔案和 jobs 狀態即時計算並更新

**改進的狀態檢測**：
- 新增 `pending` 狀態檢測
- 狀態流程：`NEW` → `INGESTED` → `SPLIT` → `PROCESSING` → `PROCESSED` → `ARCHIVED`
- `SEALED` 僅保留為舊資料相容狀態，不作為新流程終態。
