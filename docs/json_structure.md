# JSON 資料結構 (JSON Structure)

> **版本**: VLM-First V2
> **格式**: JSON / TypeScript Interface
> **用途**: 定義 VLM 識別結果的標準輸出格式。

本文件定義 VLM (Visual Language Model) 輸出的標準 JSON 結構。

---

## 核心識別結果 (`vlm_result`)

對應資料庫欄位：`jobs.vlm_result_json`。

### 範例 (Example)

```json
{
  "receipt_type": "電子發票證明聯",
  "header": {
      "supplier": "7-ELEVEN", 
      "buyer": "99999999", 
      "invoice_id": "AB12345678", 
      "voucher_id": "VCH-001",
      "date": "2024-01-15"
  }, 
  "items": [
      {
          "name": "美式咖啡大杯", 
          "qty": 1, 
          "price": 45, 
          "total": 45,
          "category": "茶水"
      }
  ], 
  "summary": {
      "subtotal": 45,
      "tax": 0,
      "total": 45
  }, 
  "verification": {
      "handwritten_total_chinese": "肆拾伍元整", 
      "stamp_shop_name": "統一超商股份有限公司",
      "qr_code_detected": true
  }
}
```

### 結構定義 (TypeScript Interface)

```typescript
interface VlmResult {
    // 收據類型
    receipt_type: "電子發票證明聯" | "免用統一發票收據" | "傳統發票" | "其他";
    
    // 檔頭資訊
    header: {
        supplier: string;      // 店家/供應商名稱
        buyer: string;         // 買受人 (統編或名稱)
        invoice_id: string;    // 發票號碼 (e.g., AB12345678)
        voucher_id?: string;   // 內部憑證編號 (e.g., VCH-001)
        date: string;          // 交易日期 (YYYY-MM-DD)
    };
    
    // 明細項目
    items: Array<{
        name: string;          // 品項名稱
        qty: number;           // 數量
        price: number;         // 單價
        total: number;         // 小計 (qty * price)
        category?: string;     // 報帳名目/費用類別 (e.g. 餐食, 茶水, 交通)
    }>;
    
    // 金額總結
    summary: {
        subtotal: number;      // 銷售額 (未稅或含稅小計)
        tax: number;           // 稅額
        total: number;         // 總計金額
    };
    
    // 驗證特徵 (用於手寫式收據驗證)
    verification: {
        handwritten_total_chinese: string | null;  // 中文大寫金額 (e.g., "壹佰元整")
        stamp_shop_name: string | null;            // 發票章上的店名
        qr_code_detected: boolean;                 // 是否偵測到 QR Code
    };
}
```

---

## 邏輯驗證結果 (`validation`)

對應資料庫欄位：`jobs.validation_json`。
由 `PythonValidator` 運算產生，不依賴 LLM。

```typescript
interface ValidationResult {
    is_valid: boolean;         // 是否通過所有核心檢核 (Required fields + Math)
    
    // 信心度計分 (0.0 - 1.0)
    // 評分權重: 欄位(30%) + 數學(30%) + 格式(10%) + OCR(15%) + 來源(15%)
    confidence: number;        
    
    // 驗證發現的問題列表
    issues: string[];          // e.g., ["總額不符: 計算=100, 申報=105", "缺少日期"]
    
    // 驗算數據
    calculated_total: number;  // 依據 items 加總的金額
    reported_total: number;    // VLM 識別出的總金額摘要
}
```

---

## 處理效能統計 (`metadata.stats`)

對應資料庫欄位：`jobs.vlm_stats`。

```typescript
interface VlmStats {
    stage: "vlm";
    processor: "VLM-OpenAI";
    model: string;             // e.g., "gemini-2.5-flash-lite"
    
    total_time_s: number;      // 總處理耗時 (秒)
    started_at: number;        // Unix Timestamp
    completed_at: number;      // Unix Timestamp
    
    // 擴充資訊 (Optional)
    token_usage?: {
        input: number;
        output: number;
        total: number;
    };
}
```

---

## 前端整合資料 (`JobDetail`)

前端 `JobEditor` 接收的完整資料結構。

```typescript
interface JobDetail {
    job_id: string;
    status: "ready" | "pending" | "running" | "done" | "failed";
    image_path: string;
    
    vlm_result: VlmResult;
    validation: ValidationResult;
    stats: VlmStats;
    
    qr_verified: boolean;      // 來自 QRHandler 的最終判斷
    manual_json?: VlmResult;   // 人工修正版本 (若有值則 UI 優先顯示)
}
```

---

## Voucher Layout (`voucher_layout.json`)

對應檔案位置：`backend/data/projects/<sanitized_project_id>/voucher_layout.json`。  
對應模型：`VoucherLayoutPayloadDraft` / `VoucherLayoutPayloadStrict`。

### 範例 (Example)

```json
{
    "globalPrefix": "D-16",
    "startIndex": 1,
    "pages": [
        {
            "pageIndex": 0,
            "fields": {
                "voucherNo": "D-16-01\nD-16-02",
                "budgetItem": "茶水費",
                "amount": "201",
                "purpose": "茶水費、影印費",
                "receiptCount": "4",
                "payDate": "2025-11-20",
                "isManuallyEdited": false
            },
            "images": [
                {
                    "jobId": "job-1771656709-5c5ee9",
                    "x": 30.0,
                    "y": 394.0,
                    "w": 74.96,
                    "h": 165.01
                }
            ]
        }
    ]
}
```

### TypeScript Interface

```typescript
interface VoucherImagePayload {
    jobId: string;
    x: number;
    y: number;
    w: number;
    h: number;
}

interface VoucherFieldsDraft {
    voucherNo: string;
    budgetItem: string;
    amount: string;
    purpose: string;
    receiptCount: string;
    payDate: string;
    isManuallyEdited: boolean;
}

interface VoucherPageDraft {
    pageIndex: number;
    fields: VoucherFieldsDraft;
    images: VoucherImagePayload[];
}

interface VoucherLayoutPayloadDraft {
    globalPrefix: string;
    startIndex: number;
    pages: VoucherPageDraft[];
}
```

### Draft 與 Strict 的差異

`POST /api/voucher/{project_id}/layout` 使用 Draft model，允許空字串，方便前端 autosave 草稿。  
`POST /api/voucher/{project_id}/generate` 使用 Strict model，只有真正要產出 PDF 的頁面才可送出，且會套用下列驗證：

1. `voucherNo`、`amount`、`receiptCount`、`payDate` 不可為空字串。
2. `amount` 必須全為數字，且數值 `<= 999999`（六格金額制度）。
3. `receiptCount` 必須全為數字。
4. `payDate` 必須是可被 `datetime.fromisoformat()` 接受的 ISO 日期字串，例如 `2025-11-20`。
5. `images[].jobId` 不可為空，且 `w`、`h` 必須大於 `0`。

### 欄位說明

| 欄位 | 型別 | 說明 |
|---|---|---|
| `globalPrefix` | `string` | 憑證號碼前綴，例如 `D-16` |
| `startIndex` | `number` | 起始流水號，用於自動重算 `voucherNo` |
| `pages[].pageIndex` | `number` | 頁面序號 |
| `pages[].fields.voucherNo` | `string` | 最終印在 PDF 上的憑證號碼 |
| `pages[].fields.budgetItem` | `string` | 預算別 |
| `pages[].fields.amount` | `string` | 金額字串，輸出時會拆成六格 |
| `pages[].fields.purpose` | `string` | 用途說明 |
| `pages[].fields.receiptCount` | `string` | 本頁發票張數 |
| `pages[].fields.payDate` | `string` | ISO 日期字串 |
| `pages[].fields.isManuallyEdited` | `boolean` | 是否已手動覆蓋用途欄位 |
| `pages[].images` | `VoucherImagePayload[]` | 本頁已放置的發票圖片矩形座標 |
