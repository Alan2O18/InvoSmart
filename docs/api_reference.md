# API 參考文檔

後端 API 端點完整參考。所有 API 皆以 `/api` 為前綴。

---

## 專案管理 (Projects)

### 列出所有專案
```http
GET /api/projects
```
**回應**: 專案陣列

### 建立專案
```http
POST /api/projects
Content-Type: application/json

{
    "name": "活動名稱"
}
```

### 取得專案詳情
```http
GET /api/projects/{project_id}
```
**備註**: 自動同步狀態

### 更新專案
```http
PUT /api/projects/{project_id}
Content-Type: application/json

{
    "name": "新名稱"
}
```

### 刪除專案
```http
DELETE /api/projects/{project_id}
```

---

## 檔案操作 (Files)

### 上傳檔案
```http
POST /api/projects/{project_id}/files/upload
Content-Type: multipart/form-data

file: <binary>
```

### 列出檔案
```http
GET /api/projects/{project_id}/files
```

### 旋轉圖片
```http
POST /api/projects/{project_id}/files/{file_id}/rotate
Content-Type: application/json

{
    "angle": 90
}
```

### 刪除檔案
```http
DELETE /api/projects/{project_id}/files/{file_id}
```

---

## 處理操作 (Processing)

### 分割發票
```http
POST /api/projects/{project_id}/split
```
**說明**: 將原始圖片分割為單張發票

### 啟動 OCR
```http
POST /api/projects/{project_id}/ocr
```
**說明**: 對所有待處理圖片執行 OCR

### 啟動 LLM
```http
POST /api/projects/{project_id}/llm
```
**說明**: 對 OCR 結果執行結構化處理

### 匯出 Excel
```http
POST /api/projects/{project_id}/export
```
**回應**: Excel 檔案路徑

### 封存專案
```http
POST /api/projects/{project_id}/seal
```
**說明**: 打包專案為 7z 檔案

---

## Job 管理 (Jobs)

### 列出 Jobs
```http
GET /api/projects/{project_id}/jobs
```
**自動同步**: 觸發專案狀態同步

### 取得單一 Job
```http
GET /api/projects/{project_id}/jobs/{job_id}
```

### 刪除 Job
```http
DELETE /api/projects/{project_id}/jobs/{job_id}
```

### 重跑 OCR
```http
POST /api/projects/{project_id}/jobs/{job_id}/rerun-ocr
```

### 重跑 LLM
```http
POST /api/projects/{project_id}/jobs/{job_id}/rerun-llm
```

---

## 人工修正 (Correction)

### 儲存修正文字
```http
POST /api/projects/{project_id}/jobs/{job_id}/manual-text
Content-Type: application/json

{
    "text": "修正後的文字內容"
}
```

### 套用修正
```http
POST /api/projects/{project_id}/jobs/{job_id}/apply-correction
```
**說明**: 從修正文字重新生成結構化資料

---

## 資料格式

### Job 狀態
| 狀態 | 說明 |
|------|------|
| `ready` | 等待處理 |
| `running` | 處理中 |
| `done` | 處理完成 |
| `failed` | 處理失敗 |
| `human_correct` | 人工修正完成 |

### 專案狀態
| 狀態 | 說明 |
|------|------|
| `NEW` | 新建立 |
| `INGESTED` | 已上傳檔案 |
| `SPLIT` | 已分割完成 |
| `PROCESSING` | 處理中 |
| `PROCESSED` | 處理完成 |
| `ARCHIVED` | 已匯出 Excel |
| `SEALED` | 已封存 |

---

## LLM 輸出格式

詳見 [json_schema.md](./json_schema.md)

```json
{
    "receipt_type": "電子發票",
    "header": {
        "supplier": "供應商名稱",
        "invoice_id": "AB12345678",
        "date": "2024-12-19",
        "tax_id": "12345678"
    },
    "items": [
        {"name": "品名", "qty": 1, "price": 100, "total": 100}
    ],
    "summary": {
        "total": 100
    },
    "audit": {
        "confidence": 0.95,
        "issues": [],
        "corrections": []
    }
}
```
