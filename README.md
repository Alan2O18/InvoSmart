# AI Agent Lab - OCR 與 LLM 處理管線

本專案是一個全端應用程式，使用 OCR（光學字元辨識）和 LLM（大型語言模型）技術來處理發票圖片。它提供了一個使用者友善的介面來管理活動（專案）、分割發票圖片、提取文字以及結構化資料。

## 技術堆疊

### 前端
*   **框架**：Vue.js 3
*   **建置工具**：Vite
*   **HTTP 客戶端**：Axios
*   **路由**：Vue Router
*   **樣式**：CSS（深色主題）

### 後端
*   **框架**：FastAPI（Python）
*   **OCR 引擎**：PaddleOCR（支援基本 OCR 和 PP-Structure 兩種模式）
  *   **基本模式**：傳統文字識別和版面重建
  *   **PP-Structure 模式**：結構化文檔分析，支援表格識別和自動旋轉校正
*   **文字處理**：Markdownify（HTML 轉 Markdown）、OpenCC（繁簡轉換）
*   **圖片處理**：OpenCV、NumPy
*   **資料庫**：SQLite（每個專案獨立）
*   **任務管理**：基於執行緒的工作佇列（CPU 用於 OCR，GPU 用於 LLM）

## 專案結構

```
AI_AGENT_LAB/
├── backend/
│   ├── routers/            # API 端點 (projects.py, websocket.py)
│   ├── services/           # 核心邏輯 (engine.py)
│   ├── processing/         # OCR 和 LLM 處理器
│   ├── utils/              # 工具函數
│   ├── main.py             # 應用程式進入點
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── views/          # Vue 元件（頁面）
│   │   ├── services/       # API 整合
│   │   └── ...
│   └── ...
├── README.md               # 本檔案
└── ...
```

## 安裝與執行

### 前置需求
*   Python 3.8+
*   Node.js 16+
*   PaddleOCR 相依套件

### 後端
1.  導航至根目錄。
2.  安裝 Python 相依套件（如果尚未安裝）。
3.  執行伺服器：
    ```bash
    uvicorn backend.main:app --reload
    ```
    後端將運行於 `http://localhost:8000`。

### 前端
1.  導航至 `frontend` 目錄。
2.  安裝相依套件：
    ```bash
    npm install
    ```
3.  執行開發伺服器：
    ```bash
    npm run dev
    ```
    前端將運行於 `http://localhost:5173`。

## 主要功能

1.  **活動管理**：建立、檢視和管理發票處理活動（專案）。
2.  **圖片分割**：自動將掃描的發票頁面分割為單獨的發票圖片。
3.  **OCR 處理**：使用 PaddleOCR 從圖片中提取文字，支援基本模式和 PP-Structure 模式。
4.  **LLM 結構化**：使用 LLM 將 OCR 文字轉換為結構化的 JSON 資料。
5.  **匯出**：將處理後的資料匯出至 Excel。
6.  **原始檔案管理**：檢視、分割和刪除原始上傳的檔案。
7.  **工作管理**：監控狀態、旋轉圖片和刪除個別工作。
8.  **自動狀態同步**：系統會根據實際處理進度自動更新活動狀態。

## OCR 引擎配置

本系統支援兩種 OCR 引擎模式，可在 `config.json` 中配置：

### 1. 基本 OCR 模式（傳統）
- 適用於簡單的文字識別場景
- 較快速，資源消耗較少
- 使用自定義版面重建演算法

**配置方式**：
```json
{
  "ocr_settings": {
    "engine": "basic",
    "language": "chinese_cht",
    "use_angle_cls": true
  }
}
```

### 2. PP-Structure 模式（推薦）
- **結構化文檔分析**：能識別表格、標題等文檔結構
- **自動旋轉校正**：自動偵測並校正文字旋轉角度
- **HTML 轉 Markdown**：將識別結果轉換為結構化的 Markdown 格式
- **繁簡轉換**：自動將簡體中文轉換為繁體中文（台灣用語）
- 適用於包含表格的收據、發票

**配置方式**：
```json
{
  "ocr_settings": {
    "engine": "ppstructure",
    "language": "chinese_cht",
    "use_angle_cls": true,
    "use_gpu": false
  },
  "ppstructure_settings": {
    "table": true,
    "ocr": true,
    "layout": true,
    "show_log": false
  },
  "text_processing": {
    "enable_traditional_conversion": true,
    "opencc_config": "s2twp.json"
  }
}
```

**PP-Structure 優勢**：
- 更準確的表格識別
- 保留文檔結構層次
- 自動處理旋轉文字
- 統一輸出為繁體中文

## API 端點

### 活動（專案）
*   `GET /api/projects`: 列出所有活動。
*   `POST /api/projects`: 建立新活動。
*   `GET /api/projects/{id}`: 取得活動狀態。
*   `PUT /api/projects/{id}`: 更新活動 metadata。
*   `DELETE /api/projects/{id}`: 刪除活動。
*   `POST /api/projects/{id}/activity_info`: 更新活動特定資訊。

### 檔案與處理
*   `POST /api/projects/{id}/add_files`: 上傳原始或已分割檔案。
*   `GET /api/projects/{id}/raw_files`: 列出原始檔案。
*   `DELETE /api/projects/{id}/raw_files/{filename}`: 刪除原始檔案。
*   `POST /api/projects/{id}/rotate/{filename}`: 旋轉圖片。
*   `POST /api/projects/{id}/run_split`: 開始所有原始檔案的分割處理。
*   `POST /api/projects/{id}/split/{filename}`: 分割特定原始檔案。
*   `POST /api/projects/{id}/run_ocr`: 開始所有工作的 OCR 處理。
*   `POST /api/projects/{id}/run_llm`: 開始所有工作的 LLM 處理。

### 工作
*   `GET /api/projects/{id}/jobs`: 列出所有工作。
*   `DELETE /api/projects/{id}/jobs/{job_id}`: 刪除特定工作。
*   `POST /api/projects/{id}/jobs/{job_id}/ocr`: 執行單一工作的 OCR。
*   `POST /api/projects/{id}/jobs/{job_id}/llm`: 執行單一工作的 LLM。

### 匯出與封存
*   `POST /api/projects/{id}/run_export`: 將活動資料匯出至 Excel。
*   `POST /api/projects/{id}/run_archive`: 封存活動（zip/7z）。
*   `POST /api/projects/{id}/regenerate`: 從 Excel 封存重新生成活動。

### 群組
*   `GET /api/groups`: 列出所有群組。
*   `POST /api/groups`: 建立或更新群組。
*   `DELETE /api/groups/{group_name}`: 刪除群組。

## 疑難排解

*   **上傳錯誤**：檢查後端控制台日誌以取得詳細錯誤訊息。
*   **圖片預覽**：確保後端伺服器正在運行以提供靜態檔案服務。

## Database Schema

The application uses a two-tier SQLite database architecture:

### Global Database (`global_projects.db`)

Located in the workspace root, this database manages all projects and user groups.

#### `projects` Table
| Column | Type | Description |
|--------|------|-------------|
| `project_id` | TEXT (PK) | Unique project identifier |
| `name` | TEXT | Project display name |
| `root_path` | TEXT | Absolute path to project directory |
| `status` | TEXT | Project status (see status codes below) |
| `created_at` | REAL | Unix timestamp of creation |
| `updated_at` | REAL | Unix timestamp of last update |
| `notes` | TEXT | Optional project notes |
| `metadata` | TEXT | JSON-encoded metadata (activity info, etc.) |

**Project Status Codes:**
- `NEW`: 新建（空）
- `INGESTED`: 已匯入原始資料
- `SPLIT`: 已切分
- `PROCESSING`: 辨識中
- `PROCESSED`: 辨識完畢
- `ARCHIVED`: 已匯出 Excel
- `SEALED`: 已封存

#### `groups` Table
| Column | Type | Description |
|--------|------|-------------|
| `group_name` | TEXT (PK) | Unique group name |
| `leader_name` | TEXT | Group leader name |

### Project Database (`jobs.db`)

Each project has its own `jobs.db` located in the project root directory.

#### `jobs` Table
| Column | Type | Description |
|--------|------|-------------|
| `job_id` | TEXT (PK) | Unique job identifier |
| `image_path` | TEXT | Path to the invoice image |
| `status` | TEXT | Job status (ready, pending, running, done, failed) |
| `stage` | TEXT | Current processing stage (load, ocr, llm, finalize) |
| `ocr_start_at` | REAL | Unix timestamp when OCR started |
| `ocr_done_at` | REAL | Unix timestamp when OCR completed |
| `llm_start_at` | REAL | Unix timestamp when LLM started |
| `llm_done_at` | REAL | Unix timestamp when LLM completed |
| `ocr_result_json` | TEXT | JSON-encoded OCR results |
| `llm_result_json` | TEXT | JSON-encoded LLM structured data |
| `manual_ocr_text` | TEXT | User-edited OCR text for manual corrections |
| `manual_updated_at` | REAL | Timestamp of last manual edit |
| `created_at` | REAL | Unix timestamp of job creation |
| `updated_at` | REAL | Unix timestamp of last update |

**Job Status Values:**
- `ready`: Ready to be processed
- `pending`: Queued for processing
- `running`: Currently being processed
- `done`: Completed successfully
- `failed`: Processing failed

**Job Stage Values:**
- `load`: Initial loading stage
- `ocr`: OCR processing stage
- `llm`: LLM structuring stage
- `finalize`: Final export stage

**Indexes:**
- `idx_jobs_status` on `status` column

#### `events` Table
| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER (PK) | Auto-increment event ID |
| `job_id` | TEXT | Reference to job |
| `event_type` | TEXT | Type of event |
| `ts` | REAL | Unix timestamp of event |
| `payload` | TEXT | JSON-encoded event data |

**Indexes:**
- `idx_events_job` on `job_id` column

### Database Configuration

All databases use the following SQLite optimizations:
- **Journal Mode**: WAL (Write-Ahead Logging)
- **Synchronous**: NORMAL
- **Foreign Keys**: ON (for project databases)
- **Connection Timeout**: 30 seconds

## Comprehensive Test Suite

The project includes a comprehensive test suite covering all Engine functions, API endpoints, and integration use cases.

### Engine Functions Tested
| Function | Category | Test Type |
|----------|----------|-----------|
| `create_project` | Project | Unit |
| `get_task_manager` | Core | Unit |
| `run_splitting` | FileOps | Unit |
| `get_raw_files` | FileOps | Unit |
| `add_project_files` | FileOps | Unit |
| `rotate_image` | FileOps | Unit |
| `delete_raw_file` | FileOps | Unit |
| `run_ocr` | Processing | Unit |
| `run_llm` | Processing | Unit |
| `run_single_ocr` | Processing | Unit |
| `run_single_llm` | Processing | Unit |
| `delete_job` | Jobs | Unit |
| `run_excel` | Export | Unit |
| `archive_project` | Export | Unit |
| `regenerate_project` | Export | Unit |

### API Endpoints Tested
| Endpoint | Method | Test Type |
|----------|--------|-----------|
| `/` | GET | Unit |
| `/` | POST | Unit |
| `/{id}` | PUT | Unit |
| `/{id}` | DELETE | Unit |
| `/{id}/status` | GET | Unit |
| `/{id}/add_files` | POST | Unit |
| `/{id}/rotate/{filename}` | POST | Unit |
| `/{id}/run_split` | POST | Unit |
| `/{id}/split/{filename}` | POST | Unit |
| `/{id}/raw_files` | GET | Unit |
| `/{id}/run_ocr` | POST | Unit |
| `/{id}/run_llm` | POST | Unit |
| `/{id}/run_export` | POST | Unit |
| `/{id}/run_archive` | POST | Unit |
| `/{id}/jobs/{job_id}/ocr` | POST | Unit |
| `/{id}/jobs/{job_id}/llm` | POST | Unit |
| `/{id}/jobs/{job_id}` | DELETE | Unit |
| `/{id}/raw_files/{filename}` | DELETE | Unit |
| `/{id}/activity_info` | POST | Unit |
| `/{id}/regenerate` | POST | Unit |
| `/groups/list` | GET | Unit |
| `/groups` | POST | Unit |
| `/groups/{name}` | DELETE | Unit |
| `/{id}/jobs` | GET | Unit |

### Integration Use Cases
1. **Full Project Lifecycle**: Create → Upload → Split → OCR → LLM → Export → Archive
2. **Manual Correction Flow**: Create → Process → Export → Human Edit → Regenerate
3. **Partial Reprocessing**: Create → Split → Single OCR → Single LLM
4. **Group Management Flow**: Create Group → Assign to Project → List → Delete
5. **File Management Flow**: Add Raw → Get Raw → Rotate → Delete Raw

### How to Run Tests
```bash
# Run all tests
pytest

# Run by category
pytest -m engine      # Engine unit tests
pytest -m api         # API unit tests
pytest -m integration # Integration use cases
```
