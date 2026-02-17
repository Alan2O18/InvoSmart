# 資料庫設計 (Database Schema)

> **版本**: VLM-First V2
> **引擎**: SQLite3 (啟用 WAL 模式)

本專案採用 **分散式 SQLite 架構**，將「全域管理」與「專案資料」分離，以確保效能並降低鎖定風險。

---

## 1. 資料庫架構總覽

系統共使用三種 SQLite 資料庫檔案：

| 資料庫類型 | 檔案路徑 | 用途 |
|---|---|---|
| **Global Projects DB** | `global_projects.db` | 管理全系統的專案列表、分組資訊、全域詞彙庫。 |
| **Suggestion DB** | `backend/data/global.db` | 專責處理自動完成 (Autocomplete) 的建議詞，獨立讀寫以優化前端反應速度。 |
| **Job DB** | `{project_root}/jobs.db` | 每個專案獨立一個 DB，儲存該專案下的所有任務 (Jobs) 與 VLM 識別結果。 |

> [!TIP]
> **WAL 模式 (Write-Ahead Logging)**
> 所有資料庫連線皆預設啟用 `PRAGMA journal_mode=WAL`，以支援高並發讀取並減少寫入鎖定。

---

## 2. 全域專案資料庫 (Global Projects DB)

### `projects` (專案列表)
儲存所有專案的基礎資訊與狀態。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `project_id` | TEXT (PK) | 專案唯一識別碼 (通常為 UUID 或 Timestamp 字串) |
| `name` | TEXT | 專案顯示名稱 |
| `root_path` | TEXT | 專案檔案在磁碟上的絕對路徑 |
| `status` | TEXT | `NEW`, `PROCESSING`, `PROCESSED`, `ARCHIVED` |
| `metadata` | TEXT (JSON) | 儲存額外資訊 (如活動日期、經辦人等) |
| `created_at` | REAL | 建立時間戳 (UTC timestamp) |
| `updated_at` | REAL | 更新時間戳 |

### `groups` (分組管理)
管理使用者的分組資訊。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `group_name` | TEXT (PK) | 組別名稱 |
| `leader_name` | TEXT | 組長姓名 |

### `vocabulary` (全域詞彙庫)
用於統計高頻詞彙，輔助校正。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | INTEGER (PK) | 自動編號 |
| `category` | TEXT | 類別 (`supplier`, `item`) |
| `term` | TEXT | 詞彙內容 |
| `frequency` | INTEGER | 出現次數 |
| `last_seen_at` | REAL | 最後出現時間 |

> **注意**: 此表主要用於後端分析，前端自動完成主要查詢 **Suggestion DB**。

---

## 3. 建議詞資料庫 (Suggestion DB)

專為前端 Autocomplete 優化的獨立資料庫。

### `suggestions`
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | INTEGER (PK) | 自動編號 |
| `category` | TEXT | `supplier`, `item_name`, `buyer`, `seller_id`... |
| `value` | TEXT | 建議詞內容 |
| `count` | INTEGER | 使用次數 (排序依據) |

---

## 4. 專案任務資料庫 (Job DB)

位於每個專案資料夾內 (`jobs.db`)，儲存識別結果。

### `jobs` (任務主表)
核心 VLM 識別結果儲存處。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `job_id` | TEXT (PK) | 任務 ID |
| `image_path` | TEXT | 圖片原始路徑 |
| `status` | TEXT | `ready`, `pending`, `running`, `done`, `failed` |
| **`vlm_result_json`** | TEXT (JSON) | VLM 識別出的原始結構化資料 (Header, Items) |
| `vlm_stats` | TEXT (JSON) | 效能統計 (Token數, 耗時) |
| `validation_json` | TEXT (JSON) | Python 邏輯驗算的結果 (Confidence, Issues) |
| `qr_verified` | INTEGER | 是否成功讀取並驗證 QR Code (0/1) |
| `manual_json_text` | TEXT (JSON) | 人工修正後的最終結果 (若有則優先顯示) |
| `created_at` | REAL | 建立時間 |

### `events` (事件日誌)
記錄任務的生命週期事件。

| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | INTEGER (PK) | 自動編號 |
| `job_id` | TEXT | 關聯的 Job |
| `event_type` | TEXT | `enqueued`, `claimed`, `vlm_completed`, `failed` |
| `payload` | TEXT (JSON) | 事件詳細資訊 |
| `ts` | REAL | 發生時間 |

---

## 5. 資料一致性策略

1. **雙軌詞彙機制**: 
   - VLM 識別出的新詞彙會寫入 **Vocabulary** (統計用)。
   - 使用者手動確認或新增的詞彙會寫入 **Suggestion DB** (前端建議用)。
   
2. **狀態同步**:
   - `Engine` 在讀取專案時，會自動掃描 `jobs.db` 的狀態，並更新 `Global DB` 中的 `projects.status`，確保列表顯示的進度是最新的。
