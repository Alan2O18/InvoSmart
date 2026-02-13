# 收據處理架構與流程規劃 (VLM-First Simplified)

> **狀態**: 正式版 (Simplified)
> **最後更新**: 2026-02-07
> **目標**: 極端簡化架構，移除本地 OCR 與分流邏輯，全面採用 VLM (Gemini Flash Lite)。

## 1. 系統總覽 (System Overview)

本系統採用 **VLM-First** 策略。所有切割後的收據影像直接送入 Gemini Flash Lite 模型進行分析，不再經過本地 OCR 或關鍵字分類。本地 QR Code 掃描僅作為電子發票的輔助驗證工具。

### 資料流向圖 (Data Flow Diagram)

```mermaid
graph TD
    Input[發票進來 Input] --> Split[切成單張 Split]
    Split --> VLM[Gemini Flash Lite 分析]
    Split --> QR[QR Code 掃描 (輔助)]
    
    VLM --> Merge{資料合併}
    QR --> Merge
    
    Merge --> Validator[邏輯驗算]
    Validator --> DB_Save[存入 DB]
    DB_Save --> Export[匯出成 Excel]
```

---

## 2. 詳細處理流程 (Detailed Processing Flows)

### 第一階段：前處理 (Phase 1: Pre-processing)

| 步驟 | 說明 |
| :--- | :--- |
| **輸入** | 上傳影像並建立專案。 |
| **分割** | `ReceiptSplitter` 將 A4 影像切割為單張收據。 |

### 第二階段：核心處理 (Phase 2: Core Processing)

此階段由 `ReceiptProcessor` 統一管理，不再分流。

1.  **VLM 分析 (Primary)**
    *   **模組**: `VisionHandler`
    *   **模型**: `gemini-2.0-flash-lite-preview-02-05` (或最新 Flash Lite 版本)
    *   **動作**: 將整張圖片送入模型，要求返回符合 Schema 的 JSON。
    *   **優勢**: 自動處理所有收據類型 (電子/手寫/長條)，無需分類邏輯。

2.  **QR Code 輔助 (Secondary)**
    *   **模組**: `QRHandler`
    *   **動作**: 嘗試掃描圖片中的 QR Code。
    *   **用途**: 若 VLM 識別的發票號碼或日期有誤，且 QR Code 清晰可讀，則以 QR Code 資料為準 (因為它是確定性的)。

3.  **邏輯驗算 (Validation)**
    *   **模組**: `PythonValidator`
    *   **動作**: 檢查金額 (單價*數量=總價)、日期格式、必填欄位。

---

## 3. 模組職責變更 (Module Responsibilities)

| 模組 | 舊職責 | **新職責** |
| :--- | :--- | :--- |
| `ReceiptProcessor` | 管理 OCR/分類/分流/LLM | **單一流程控制** (VLM -> QR -> Merge) |
| `VisionHandler` | 僅處理手寫收據 | **核心處理器** (處理所有類型) |
| `RapidOCRHandler` | 主要文字提取 | **(移除/停用)** |
| `KeywordClassifier` | 收據分類 | **(移除/停用)** |
| `LLMHandler` | 文本修正/提取 | **(輔助/備用)** 僅用於純文本任務 |
| `QRHandler` | 電子發票主要資料源 | **輔助驗證** (提供 Ground Truth) |

---

## 4. 下一步 (Next Steps)

*   [ ] 重構 `ReceiptProcessor`，移除 `process_ocr_only` 與 `process_llm_only`。
*   [ ] 實作單一 `process(image)` 方法。
*   [ ] 更新 `VisionHandler` 以支援通用 Prompt。
*   [ ] 移除 `RapidOCR` 相關依賴與程式碼。
