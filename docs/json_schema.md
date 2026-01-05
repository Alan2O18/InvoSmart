# JSON Schema 規範

> 更新日期: 2024-12-19

本文件定義 `jobs.db` 中 JSON 欄位的結構規範。

---

## ocr_result_json

OCR 前處理輸出的純文字結果。

```typescript
interface OcrResult {
    text: string;    // reconstruct_layout 後的純文字
    type: string;    // 收據類型：電子發票 | 免用統一發票收據 | 其他收據
}
```

---

## llm_result_json

LLM/VLM/QR 處理後的結構化資料。

```typescript
interface LlmResult {
    receipt_type: "電子發票" | "免用統一發票收據" | "其他收據";
    
    // 電子發票專用 - QR Code 解碼結果
    qr_decode?: {
        invoice_id: string;    // 發票號碼 (AB12345678)
        date: string;          // 發票日期 (YYYY-MM-DD)
        seller_id: string;     // 賣方統編
        buyer_id?: string;     // 買方統編
        total: number;         // 總金額
        random_code: string;   // 隨機碼
        raw_data: string;      // 原始 QR 字串
    };
    
    // 通用欄位
    header: {
        supplier?: string;     // 商家名稱
        buyer?: string;        // 買受人
        invoice_id?: string;   // 發票號碼
        date?: string;         // 日期
    };
    
    items: Array<{
        name: string;          // 品名
        qty: number | null;    // 數量
        price: number | null;  // 單價
        total: number | null;  // 小計
    }>;
    
    summary: {
        total: number | null;  // 總金額
    };
    
    verification?: {
        handwritten_total_chinese?: string;  // 中文大寫金額
        stamp_shop_name?: string;            // 店章店名
    };
    
    audit: {
        confidence: number;                  // 信心分數 0-1
        issues: string[];                    // 發現的問題
        corrections: Array<{
            source: "py_validator" | "gemma" | "human";
            timestamp: number;               // Unix 時間戳
            description?: string;            // 修正說明
        }>;
    };
}
```

---

## ocr_stats

PaddleOCR 前處理效能統計。

```typescript
interface OcrStats {
    engine: string;           // "paddleocr"
    language: string;         // "chinese_cht"
    total_time_s: number;     // 總處理時間（秒）
    text_blocks_count: number; // 識別的文字區塊數
    started_at: number;       // 開始時間戳
    completed_at: number;     // 完成時間戳
}
```

---

## llm_stats

LLM 處理階段效能統計，為 JSON 陣列，長度 1-2。

```typescript
type LlmStats = Array<{
    stage: "primary" | "correction";
    processor: "VLM" | "LLM" | "QR" | "GEMMA";
    model: string;            // 模型名稱
    total_time_s: number;     // 總處理時間
    ttft_s: number;           // 首個 Token 回應時間
    prompt_tokens: number;    // Prompt Token 數
    prompt_time_s: number;    // Prompt 處理時間
    prompt_speed_tps: number; // Prompt 處理速度 (tok/s)
    generation_tokens: number;     // 生成 Token 數
    generation_time_s: number;     // 生成時間
    generation_speed_tps: number;  // 生成速度 (tok/s)
    issues_count?: number;    // 修正的問題數（僅 correction 階段）
    started_at: number;
    completed_at: number;
}>;
```

---

## 處理器類型對照

| processor | 說明 | 使用模型 |
|-----------|------|---------|
| `VLM` | 手寫收據視覺識別 | qwen3-vl:2b |
| `LLM` | 傳統發票文字處理 | qwen3:1.7b |
| `QR` | 電子發票 QR Code 解碼 | - |
| `GEMMA` | 二次校驗修正 | gemma3:4b |
