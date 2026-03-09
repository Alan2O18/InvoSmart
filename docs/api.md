# API 介面規格 (API Reference)

> **版本**: V2.1 (VLM-First + Voucher Editor)
> **Base URL**: `/api`

本文件定義目前後端實際對外提供的 REST API 與 WebSocket 端點。路由以 `backend/main.py` 與 `backend/routers/` 的現況為準。

---

## 1. 專案管理 (Projects)
`Tag: projects`

### 列出專案
`GET /projects/`
- **回應**: 專案列表 (JSON Array)

### 建立專案
`POST /projects/`
- **Content-Type**: `multipart/form-data`
- **參數**:
    - `project_id`: 專案 ID
    - `files`: 原始圖片檔案列表
    - `metadata`: JSON 字串，可包含 `name`、`budgetExpense` 等欄位

### 更新專案 Metadata
`PUT /projects/{project_id}`
- **Content-Type**: `application/json`
- **Body**: 任意 metadata 物件

### 刪除專案
`DELETE /projects/{project_id}`

### 取得專案完整資料
`GET /projects/{project_id}/detail`
- **功能**: 回傳完整專案 payload，包含 `metadata`
- **用途**: Voucher Editor 讀取預算別等專案層級資料

### 取得專案狀態
`GET /projects/{project_id}`
- **功能**: 取得專案狀態摘要，並先同步 jobs 狀態到資料庫

### 更新活動資訊
`POST /projects/{project_id}/activity_info`
- **Body**: 任意 JSON 物件
- **功能**: 合併更新到專案 metadata

### 舊版快速產生憑證 PDF
`POST /projects/{project_id}/generate-voucher-pdf`
- **狀態**: Deprecated
- **說明**: 舊版憑證黏貼 PDF 下載入口，保留相容用途；新流程請改用 Voucher API

---

## 2. 檔案管理 (Files)
`Tag: projects`

> [!NOTE]
> `files.py` 實際是掛在 `/api/projects` 之下，而不是獨立 `/api/files`。

### 新增專案檔案
`POST /projects/{project_id}/add_files`
- **Content-Type**: `multipart/form-data`
- **欄位**:
    - `type`: 檔案類型標記
    - `files`: 檔案列表

### 旋轉原始圖片
`POST /projects/{project_id}/rotate/{filename}?angle=90`

### 取得原始檔列表
`GET /projects/{project_id}/raw_files`

### 刪除原始檔
`DELETE /projects/{project_id}/raw_files/{filename}`

---

## 3. 任務管理 (Jobs)
`Tag: projects`

### 列出專案所有 Jobs
`GET /projects/{project_id}/jobs`

### 取得 Job 詳情
`GET /projects/{project_id}/jobs/{job_id}/details`
- **回應**: 包含 `vlm_result`, `validation`, `manual_json` 等欄位

### 刪除 Job
`DELETE /projects/{project_id}/jobs/{job_id}`

### 重跑單一 Job 處理
`POST /projects/{project_id}/jobs/{job_id}/process`

### 儲存人工修正 JSON
`PUT /projects/{project_id}/jobs/{job_id}/json`
- **Body**:

```json
{
    "json_data": {}
}
```

---

## 4. 批次處理 (Processing)
`Tag: projects`

### 執行分割
`POST /projects/{project_id}/run_split`

### 單檔分割
`POST /projects/{project_id}/split/{filename}`

### 執行整個專案的 VLM 處理
`POST /projects/{project_id}/run_processing`

### 匯出 Excel
`POST /projects/{project_id}/run_export`

### 匯出 Word
`POST /projects/{project_id}/run_word_export`
- **回應**: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`

### 封存專案
`POST /projects/{project_id}/run_archive`

---

## 5. 建議詞 (Suggestions)
`Tag: suggestions`

### 搜尋建議詞
`GET /suggestions`
- **參數**:
    - `category`: 必填，例 `supplier`, `item_name`, `buyer`, `seller_id`, `buyer_id`, `stamp_shop_name`
    - `q`: 搜尋關鍵字
    - `limit`: 回傳數量上限，預設 `20`

### 新增單筆建議詞
`POST /suggestions`

```json
{
    "category": "supplier",
    "value": "7-ELEVEN"
}
```

### 批次新增建議詞
`POST /suggestions/bulk`

```json
{
    "category": "item_name",
    "values": ["拿鐵", "美式"]
}
```

---

## 6. 系統設定 (Config)
`Tag: config`

### 取得目前設定
`GET /config/`
- **注意**: 敏感資訊如 `vision_settings.api_key` 會以遮罩形式回傳

### 更新設定
`POST /config/`
- **Body**: 完整或局部設定 JSON
- **安全機制**: 若前端傳回遮罩後的 API key，後端會保留舊值

---

## 7. Voucher API
`Tag: voucher`

### 取得憑證模板與可用發票
`GET /voucher/{project_id}/template`
- **回應**:
    - `templatePng`: Base64 PNG 預覽
    - `projectMeta`: 專案摘要
    - `invoices`: 可用發票清單，包含 `jobId`, `imageUrl`, `result`

### 取得單張發票圖片
`GET /voucher/{project_id}/image/{job_id}?thumb=true`
- **說明**: `thumb=true` 時回傳縮圖，否則回傳較高品質 JPEG

### 取得 KaiU 字型
`GET /voucher/fonts/kaiu.ttf`
- **回應**: `font/ttf`

### 取得 Voucher 文字欄位設定
`GET /voucher/text-config`
- **回應**:
    - `version`: 目前欄位設定版本 (V0.0.7 起為六格金額制度)
    - `font`: 前端預覽字型設定
    - `fields.amount`: 包含 `xList`, `padLength`, `digitPolicy`, `legacyMaxDigits`

### 讀取排版草稿
`GET /voucher/{project_id}/layout`
- **回應**: `layout.json` 結構，見 `docs/json_structure.md`

### 儲存排版草稿
`POST /voucher/{project_id}/layout`
- **Body**: `VoucherLayoutPayloadDraft`

### 產出憑證 PDF
`POST /voucher/{project_id}/generate`
- **Body**: `VoucherLayoutPayloadStrict`
- **回應**: `application/pdf` 檔案串流 (`FileResponse`)
- **Strict 金額規則**: `amount` 必須為純數字且 `<= 999999` (六格)

---

## 8. PDF 處理
`Tag: pdf`

### 上傳 PDF 並加入背景處理
`POST /pdf/{project_id}/pdf`
- **Content-Type**: `multipart/form-data`
- **欄位**: `files`

### 提交 PDF 編輯指令
`POST /pdf/{project_id}/{job_id}/commands`
- **Body**: 可包含 `page_order`, `stamps`, `texts` 等指令

### 下載處理後 PDF
`GET /pdf/{project_id}/{job_id}/download`
- **說明**: 若壓縮後 PDF 存在則優先回傳，否則回傳原始 PDF

---

## 9. 分組管理 (Groups)
`Tag: projects`

### 列出群組
`GET /projects/groups/list`

### 新增或更新群組
`POST /projects/groups`

```json
{
    "group_name": "第一組",
    "leader_name": "王小明"
}
```

### 刪除群組
`DELETE /projects/groups/{group_name}`

---

## 10. 人工校正 (Correction)
`Tag: projects`

### 儲存人工文字修正
`PUT /projects/{project_id}/jobs/{job_id}/manual`

```json
{
    "manual_text": "修正後文字"
}
```

---

## 11. WebSocket
`Tag: websocket`

### 即時監看專案狀態
`WS /ws/{project_id}`
- **回傳內容**:
    - `jobs`: 目前 jobs 清單
    - `progress`: 專案進度/狀態摘要

---

## 狀態碼說明
- `200 OK`: 成功
- `404 Not Found`: 專案、Job 或檔案不存在
- `422 Unprocessable Entity`: 請求 body 未通過 Pydantic 驗證
- `500 Internal Server Error`: 伺服器內部錯誤
