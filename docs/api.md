# API 介面規格 (API Reference)

> **版本**: V2 (VLM-First)
> **Base URL**: `/api`

本文件定義後端提供的所有 RESTful API 端點。

---

## 1. 專案管理 (Projects)
`Tag: projects`

### 列出專案
`GET /projects`
- **回應**: 專案列表 (JSON Array)

### 建立專案
`POST /projects`
- **Content-Type**: `multipart/form-data`
- **參數**:
    - `project_id`: (Text) 專案 ID
    - `files`: (File List) 原始圖片檔案
    - `metadata`: (Text, Optional) JSON 字串，包含 `name` 等資訊

### 取得專案詳情
`GET /projects/{project_id}`
- **功能**: 取得專案狀態與 Metadata (會自動觸發狀態同步)

### 更新專案
`PUT /projects/{project_id}`
- **Content-Type**: `application/json`
- **Body**: `{ "name": "新名稱", ... }`

### 刪除專案
`DELETE /projects/{project_id}`

### 更新活動資訊
`POST /projects/{project_id}/activity_info`
- **Body**: 任意 JSON 物件 (將合併至專案 Metadata)

### 取得 Job ID 列表 (導航用)
`GET /projects/{project_id}/job-ids`
- **回應**: 僅包含 `job_id`, `status`, `image_path` 的輕量列表

---

## 2. 任務管理 (Jobs)
`Tag: jobs`

### 列出所有 Jobs
`GET /projects/{project_id}/jobs`
- **回應**: 完整 Job 物件列表

### 取得 Job 詳情 (編輯器用)
`GET /projects/{project_id}/jobs/{job_id}/details`
- **回應**: 包含 `vlm_result`, `validation`, `manual_json` 等詳細資訊

### 刪除 Job
`DELETE /projects/{project_id}/jobs/{job_id}`

### 單一任務處理
`POST /projects/{project_id}/jobs/{job_id}/process`
- **功能**: 強制重跑單一 Job 的 VLM 處理

### 儲存人工修正
`PUT /projects/{project_id}/jobs/{job_id}/json`
- **Body**: `{ "json_data": { ... } }`

---

## 3. 批次處理 (Processing)
`Tag: processing`

### 執行分割
`POST /projects/{project_id}/run_split`
- **功能**: 對 `原始輸入` 資料夾中的檔案執行裁切與分割

### 單檔分割
`POST /projects/{project_id}/split/{filename}`

### 執行 VLM 辨識 (全專案)
`POST /projects/{project_id}/run_processing`
- **功能**: 將所有 `ready` 或 `failed` 狀態的 Job 加入佇列進行 VLM 分析

### 匯出 Excel
`POST /projects/{project_id}/run_export`
- **回應**: `{ "excel_path": "..." }`

### 封存專案
`POST /projects/{project_id}/run_archive`
- **功能**: 建立 7z 封存檔

---

## 4. 建議詞 (Suggestions)
`Tag: suggestions`

### 搜尋建議詞
`GET /suggestions`
- **參數**:
    - `category`: (Required) `supplier`, `item_name`, `buyer`, `seller_id`, `buyer_id`
    - `q`: (Optional) 搜尋關鍵字
    - `limit`: (Optional, default 20)

### 新增建議詞
`POST /suggestions`
- **Body**: `{ "category": "supplier", "value": "7-ELEVEN" }`

### 批次新增
`POST /suggestions/bulk`
- **Body**: `{ "category": "item_name", "values": ["拿鐵", "美式"] }`

---

## 5. 系統設定 (Config)
`Tag: config`

### 取得目前設定
`GET /config`
- **注意**: 敏感資訊 (如 `api_key`) 會以 `***` 遮罩回傳。

### 更新設定
`POST /config`
- **Body**: 完整的設定 JSON 物件
- **安全機制**: 若 `vision_settings.api_key` 為遮罩值 (含 `***`)，後端將保留原有的 Key 不做修改。

---

## 狀態碼說明
- `200 OK`: 成功
- `404 Not Found`: 專案或 Job 不存在
- `500 Internal Server Error`: 伺服器內部錯誤 (請查看 Log)
