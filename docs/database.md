# 資料庫設計 (Database Schema)

> **版本**: VLM-First V2 (SQLAlchemy ORM)
> **引擎**: SQLite3 (啟用 WAL 模式, AsyncIO)

本專案採用 **集中式 SQLite (Unified Global SQLite) 加上 SQLAlchemy 2.0 Async ORM** 架構，解決了初期的分散式資料庫維護不易與鎖定等待的問題。

---

## 1. 資料庫架構總覽

系統現在僅依賴單一核心資料庫檔案：

| 資料庫類型 | 檔案路徑 | 用途 |
|---|---|---|
| **Global DB** | `backend/data/global.db` (支援 `config.json` 動態配置路徑) | 集中管理所有的專案、任務、發票細項、組別與前端自動完成詞彙庫。 |

> [!TIP]
> **並行與效能 (Concurrency & Performance)**
> - 連線強制啟用 `PRAGMA foreign_keys=ON`。
> - 預設啟用 `PRAGMA journal_mode=WAL`，支援高並發讀取並減少寫入鎖定。
> - `AsyncEngine` 連線池設定為 `NullPool`，將鎖定管理與併發處理的職責交還給底層 SQLite WAL 防禦層，解決了過往 "Database is Locked" 的錯誤。

---

## 2. ORM 模型設計 (Models)

系統總共規劃 6 張核心資料表，由 `backend/database/models.py` 統一管理，並經由 Alembic 自動遷移。

### 1. `projects` (專案)
管理專案實體的檔案夾關聯與基礎資訊。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `project_id` | String (PK) | 專案唯一識別碼 |
| `name` | String | 專案名稱 |
| `root_path` | String | 專案對應的系統目錄絕對路徑 |
| `status` | String | 處理進度狀態 |
| `meta_data` | JSON | 其他元資料 |

### 2. `jobs` (任務)
每張圖片與發票的處理任務。外鍵關聯至專案。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `job_id` | String (PK) | 任務唯一識別碼 |
| `project_id` | String (FK) | 關聯專案的 ID |
| `image_path` | String | 圖片相對路徑 |
| `status` | String | `ready`, `pending`, `running`, `done`, `failed` |
| `vlm_result_json` | Text | VLM 回傳的原始 Header JSON |
| `manual_json_text` | Text | 使用者覆寫校正的結果 |

### 3. `invoice_items` (發票細項)
將原本封裝在 JSON 內的商品細項正規化為一對多關聯表 (One-to-Many)，此為唯一的真理來源 (Source of Truth)。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | 流水號 |
| `job_id` | String (FK) | 歸屬之任務 ID |
| `category` | String | 商品類別 |
| `description` | String | 商品名稱 / 描述 |
| `quantity` | Float | 數量 (支援小數) |
| `price` | Float | 單價 |

### 4. `events` (事件日誌)
非同步任務的生命週期追蹤 (稽核用)。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | 流水號 |
| `job_id` | String (FK) | 目標任務 |
| `event_type` | String | `enqueued`, `claimed`, `vlm_completed`, `failed` |

### 5. `groups` (分組)
管理使用者群體。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `group_name` | String (PK) | 組別名稱 |
| `leader_name` | String | 組長稱呼 |

### 6. `suggestions` (建議詞彙)
提供前端編輯器 Autocomplete 自動完成。合併了舊版的 `vocabulary` 統計機制。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | Integer (PK) | 流水號 |
| `category` | String, Index | 詞彙屬性 (`supplier`, `item_name` 等) |
| `value` | String | 詞彙內文 |
| `count` | Integer | 被使用的頻率次數 |

---

## 3. 資料移轉機制 (Alembic)

> [!WARNING]
> 分散式 `{project}/jobs.db` 的檔案架構已全面捨棄。

本系統依賴 **Alembic** 進行基於 SQLAlchemy ORM 的版本控制。
為了適應自訂組態檔中對資料庫路徑的要求，`alembic/env.py` 已實作動態解析，在執行 `alembic upgrade head` 時會優先由 `config.json` 抽取路徑並注入 Alembic 設定檔。
