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
      "date": "2024-01-15"
  }, 
  "items": [
      {
          "name": "美式咖啡大杯", 
          "qty": 1, 
          "price": 45, 
          "total": 45
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
        date: string;          // 交易日期 (YYYY-MM-DD)
    };
    
    // 明細項目
    items: Array<{
        name: string;          // 品項名稱
        qty: number;           // 數量
        price: number;         // 單價
        total: number;         // 小計 (qty * price)
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
