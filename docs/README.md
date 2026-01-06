# 文檔目錄

> **AI Agent Lab** OCR 與 LLM 收據處理系統

---

## 快速導覽

| 文檔 | 說明 | 適合對象 |
|-----|------|---------|
| [quickstart.md](./quickstart.md) | 快速開始指南 | 🟢 新手 |
| [processing_pipeline.md](./processing_pipeline.md) | **處理流程說明** | 🟢 所有人 |
| [api_reference.md](./api_reference.md) | API 端點參考 | 🔵 前端開發 |
| [developer_guide.md](./developer_guide.md) | 開發者指南 | 🟣 後端開發 |
| [backend_architecture.md](./backend_architecture.md) | 系統架構分析 | 🟣 後端開發 |

---

## 處理流程

```
掃描 A4 → 分割 → OCR → 分類 → 分流處理 → JSON → 人工查核
                         ↓
              ┌──────────┼──────────┐
              A 手寫     B 電子     C 其他
```

詳見 [processing_pipeline.md](./processing_pipeline.md)

---

## 資料格式

| 文檔 | 說明 |
|-----|------|
| [json_schema.md](./json_schema.md) | LLM 輸出 JSON 格式規範 |
| [database_schema.md](./database_schema.md) | 資料庫結構 |
| [empty_receipt_template.json](./empty_receipt_template.json) | 空白收據範本 |

---

## 測試

| 文檔 | 說明 |
|-----|------|
| [testing_plan.md](./testing_plan.md) | 測試計畫 |
| [testing_todo.md](./testing_todo.md) | 測試待辦事項 |

---

## 測試資料

| 目錄 | 內容 |
|-----|------|
| `test_images/` | 測試用收據圖片 |
| `regions/` | 實體分區 OCR 測試結果 |
| `virtual_regions/` | 虛擬分區 OCR 測試結果 |
