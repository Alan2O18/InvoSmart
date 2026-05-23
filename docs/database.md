# 資料庫設計 (Database Schema)

> **版本**: VLM-First V2.5 (v0.0.25)
> **引擎**: SQLite3 (WAL 模式, AsyncIO, SQLAlchemy 2.0)
> **更新日期**: 2026-05-23

本專案採用 **集中式 SQLite (Unified Global SQLite) + SQLAlchemy 2.0 Async ORM** 架構，加上輕量 **JSON 檔案式倉庫**處理 PDF 任務與印章模板元數據。

---

## 1. 資料庫架構總覽

| 儲存類型 | 路徑/位置 | 用途 |
|---|---|---|
| **Global SQLite DB** | `config.json` 動態配置（預設 `workspace/global.db`）| 專案、任務、細項、人員、印章、建議詞彙 |
| **PDF Task JSON** | `backend/data/pdf_tasks/<task_id>/task.json` | PDF 任務元數據（頁數、蓋章紀錄）|
| **PDF Working File** | `backend/data/pdf_tasks/<task_id>/working.pdf` | PDF 任務作業中主體檔 |
| **Stamp Template JSON** | `backend/data/stamp_templates/<id>/template.json` | 印章模板配置 |
| **Voucher Layout JSON** | `workspace/<project_id>/voucher_layout.json` | 憑證編輯器草稿 |

> [!TIP]
> **並行與效能**
> - `PRAGMA foreign_keys=ON` — 外鍵強制
> - `PRAGMA journal_mode=WAL` — 高並發讀取、減少寫入鎖定
> - `AsyncEngine` 連線池採 `NullPool`，解決歷史性 "Database is Locked" 錯誤

---

## 2. SQLite ORM 模型設計 (Models)

系統共 7 張核心資料表，由 `backend/database/models.py` 統一管理，Alembic 版本控制。

### 2.1 `projects` (專案)

| 欄位 | 類型 | 說明 |
|---|---|---|
| `project_id` | String (PK) | 專案唯一識別碼 |
| `name` | String | 專案名稱 |
| `root_path` | String | 系統目錄絕對路徑 |
| `status` | String | `NEW`, `SPLIT`, `PROCESSING`, `PROCESSED`, `ARCHIVED`, `SEALED` |
| `meta_data` | JSON | 活動基本資訊、財務預算等擴充 metadata |
| `notes` | Text | 備注欄位 |
| `created_at` / `updated_at` | Float (Unix timestamp) | |

### 2.2 `jobs` (任務)

| 欄位 | 類型 | 說明 |
|---|---|---|
| `job_id` | String (PK) | UUID |
| `project_id` | String (FK → projects) | |
| `image_path` | String | 分割後圖片路徑（單張圖）|
| `source_pdf_path` | String, nullable | 原始 PDF 路徑（PDF 任務）|
| `compressed_pdf_path` | String, nullable | 壓縮後 PDF |
| `status` | String, indexed | `ready`, `pending`, `running`, `done`, `failed` |
| `pdf_status` | String, indexed | `uploaded`, `ocr_done`, `needs_review`, `compressing`, `completed` |
| `pdf_commands_json` | Text | 前端蓋章/排版指令 |
| `vlm_result_json` | Text | 原始 VLM 辨識 JSON（UI/Export 組裝用）|
| `vlm_raw_json` | Text | 不可變 VLM 原始結果（稽核留存）|
| `vlm_stats` | Text | VLM token 統計 |
| `validation_json` | Text | PythonValidator 結果 |
| `voucher_id` | String | 正規化發票號碼 |
| `purpose` | String | 正規化用途說明 |
| `supplier` | String | 正規化供應商 |
| `invoice_date` | String | 正規化日期 (YYYY-MM-DD) |
| `total_amount` | Float | 正規化總金額 |
| `qr_verified` | Integer | QR 驗證旗標 (`1`/`0`) |
| `manual_json_text` | Text | 使用者手動校正的最終 JSON |
| `manual_updated_at` | Float | 手動更新時間戳 |
| `source_format` | String | 原始格式 (`jpg`, `jxl`, `png`) |
| `preview_cache_path` | String | 最新預覽快取絕對路徑 |

> [!IMPORTANT]
> **v0.0.25 變更**：`flattened_data` 和 `flattening_status` 欄位已**完全移除**。
> 正規化欄位（`voucher_id`、`supplier`、`invoice_date`、`total_amount`、`purpose`）為唯一真實來源；
> 展平邏輯保留於 `backend/processing/flattening.py` 供 WordExporter 動態計算使用。

### 2.3 `invoice_items` (發票細項)
將 JSON 內的商品細項正規化為 One-to-Many 關聯表。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | 自增流水號 |
| `job_id` | String (FK → jobs) | |
| `category` | String | 商品類別 |
| `description` | String | 商品名稱 |
| `quantity` | Float | 數量（支援小數）|
| `price` | Float | 單價 |
| `total` | Float | 小計 |
| `remark` | String | 備注 |

### 2.4 `events` (事件日誌)

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | |
| `job_id` | String (FK → jobs) | |
| `event_type` | String | `enqueued`, `claimed`, `vlm_completed`, `failed` |
| `ts` | Float | Unix timestamp |
| `payload` | Text | JSON 附加資訊 |

### 2.5 `persons` (人員)
v0.0.20 新增，取代舊版 `groups` 模型。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | |
| `name` | String (unique) | 姓名或虛擬實體名稱 |
| `role` | String | `handler`, `activity_general_affairs`, `general_affairs_head`, `president`, `advisor`, `fin_original`, `fin_audited`, `club_seal` |
| `is_virtual` | Boolean | `True` = 虛擬實體（社團大章、財務章）|
| `created_at` | Float | |

### 2.6 `stamps` (印章)

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | |
| `owner_id` | Integer (FK → persons) | |
| `category` | String | 簡化為 `personal`；位置由 `Person.role` 決定 |
| `image_path` | String | 印章圖片絕對路徑 |
| `created_at` | Float | |

### 2.7 `suggestions` (建議詞彙)

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | |
| `category` | String, indexed | `supplier`, `item_name`, `person_name`, `group_name`, `location`, `budget_income_item`, `expense_category` |
| `value` | String | 詞彙內文 |
| `count` | Integer | 使用頻率 |
| `last_used_at` | Float | |

### 2.8 `groups` (舊版分組 — DEPRECATED)
> [!WARNING]
> `groups` 表已廢棄，保留以向後相容。v0.0.20 起請使用 `persons` 表。

---

## 3. JSON 檔案式倉庫 (File-based Repositories)

### 3.1 PdfTaskRepository
```
backend/data/pdf_tasks/
└── <task_id>/
    ├── task.json        # 元數據 (page_count, stamps[], updated_at)
    └── working.pdf      # 作業主體 PDF
```

### 3.2 StampTemplateRepository
```
backend/data/stamp_templates/
└── <template_id>/
    └── template.json    # 模板配置 (name, zones[], created_at)
```

### 3.3 VoucherLayoutRepository
```
workspace/
└── <project_id>/
    └── voucher_layout.json   # 憑證編輯器草稿 (pages[], globalPrefix, startIndex)
```

---

## 4. 資料移轉機制 (Alembic)

> [!WARNING]
> 舊版分散式 `{project}/jobs.db` 架構已全面廢棄，所有資料集中於 `global.db`。

系統依賴 **Alembic** 進行 ORM schema 版本控制。`alembic/env.py` 實作動態路徑解析，執行 `alembic upgrade head` 時優先從 `config.json` 讀取 DB 路徑。

```bash
# 套用最新 migration
alembic upgrade head

# 查看目前版本
alembic current
```

---

## 5. v0.0.25 重大變更摘要

| 變更項目 | 說明 |
|---|---|
| 移除 `flattened_data` 欄位 | 使用正規化欄位取代 JSON blob |
| 移除 `flattening_status` 欄位 | 狀態追蹤改由 job.status 直接管理 |
| 新增 `PdfTaskRepository` | JSON 檔案式 PDF 任務持久化 |
| 新增 `StampTemplateRepository` | JSON 檔案式印章模板持久化 |
| `job_repository.py` cleanup | 移除 ~28 個 `flattened_data` 相關方法與查詢 |
