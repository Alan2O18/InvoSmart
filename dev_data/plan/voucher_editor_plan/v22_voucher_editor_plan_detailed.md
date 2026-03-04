# 憑證黏貼編輯器 — 究極計畫 v22 (規格釐清與細節展開版)

## 0. 詞彙表 (Glossary)
- **發票 (Invoice/Receipt)**：使用者上傳的各種消費單據原稿圖片。
- **底模 (Template)**：空白的系統表單（如 `憑證黏貼用紙.pdf`）。
- **憑證 (Voucher)**：將多張發票依據會計規範，黏貼於**底模**之上，並填妥各項申報欄位後產出的最終 PDF 檔案。
- **頁面 (Page)**：一張憑證可能由多個物理分頁組成（例如 10 張發票需要 3 頁底模才能貼完）。編輯器中的一頁對應未來產出的一張 PDF 頁面。

---

## 1. 資料流程圖 (Data Flow)

```mermaid
graph TD
    A[上傳發票圖片] --> B[VLM 辨識提取 JSON]
    B --> C[人工審核修正 (存入 manual_json)]
    C --> D[進入 Voucher Editor]
    D --> E[GET /template 取得底模與發票選單]
    E --> F[拖曳發票至 Canvas 黏貼]
    F --> G[左側面板即時計算金額/日期/用途]
    G --> H[人工再次微調覆寫欄位]
    H --> I[POST /generate 產出最終憑證 PDF]
```

---

## 2. API 端點清單 (API Specifications)

| Method | Path | Request/Response 說明 |
|:---|:---|:---|
| `GET` | `/api/voucher/{project_id}/template` | **Res**: `{ templatePng: str(base64), projectMeta: dict, invoices: [ { jobId: str, imageUrl: str, vlmResult: dict, amount: number } ] }` |
| `GET` | `/api/voucher/image/{job_id}?thumb=true` | **Res**: 回傳 `image/webp` 或原圖 (Image Proxy) |
| `GET` | `/api/voucher/{project_id}/layout` | **Res**: VoucherLayoutPayload (讀取草稿) |
| `POST`| `/api/voucher/{project_id}/layout` | **Req**: VoucherLayoutPayload <br> **Res**: `{ status: "success" }` (存入草稿) |
| `POST`| `/api/voucher/{project_id}/generate` | **Req**: VoucherLayoutPayload <br> **Res**: `{ pdfUrl: str }` (啟動 PyMuPDF 寫入) |

---

## 3. Canvas 座標系對照表 (Coordinate Map)

> 基於 `憑證黏貼用紙.pdf` (595×842 pts，即 210×297 mm A4 尺寸)

```
(0,0) ┌─────────────────────────────┐ (595,0)
      │      [ 憑證黏貼用紙 ]       │
      │ ┌───────────────────────┐ │ (71,185)
      │ │ 表頭資訊 (科目/用途等)│ │
      │ └───────────────────────┘ │ (524,320)
      │ [簽章列1] 112,340→491,394 │
      ├───────────────────────────┤ (30,394)
      │                           │
      │    ✅ 可黏貼範圍 Safe Zone│
      │    (寬 535 x 高 336 pts)  │
      │                           │
      ├───────────────────────────┤ (565,730)
      │ [簽章列2] 89,730→507,804  │
(0,842)└─────────────────────────────┘(595,842)
```

---

## 4. 關鍵規格與疑慮釐清 (針對 1-8 項)

### 4.1 金額格式與填充範例 (7位數)
- **規格確認**：底模表頭的金額欄位共 7 格，對應 `[佰萬][拾萬][萬][仟][佰][拾][元]`，上限為 `9,999,999`。
- **資料型別**：Frontend Payload 統一傳送 `String`。後端使用 Regex 嚴格驗證是否為純數字字串。
- **填充範例**：
  - `146` → `[※][※][※][※][1][4][6]`
  - `4607` → `[※][※][※][4][6][0][7]`
  - `250000` → `[※][2][5][0][0][0][0]`

### 4.2 非法日期與使用者的解鎖 UX
- **機制**：如果拉上畫布的發票中，有任何一張的日期 `""` 或 `None`。
- **UX 流程**：
  1. 系統亮紅燈，並將「產出 PDF」按鈕 Disabled。
  2. 左側面板的「支付日期」欄位會顯示 `[！含有無效日期]` 並**開放手動輸入 (Manual Override)**。
  3. 使用者**直接在該欄位手動輸入正確的日期 (如 114/05/12)**，系統即解除鎖定，允許產出。

### 4.3 台幣小數進位邏輯 (會計不可篡改原則)
- **修正**：為了遵守會計準則，**系統不可擅自使用 `Math.ceil()` 竄改小數**。
- **機制**：若當頁加總出現小數（如 `145.5`）：
  1. 金額欄位標示黃色背景 🟡。
  2. 「產出 PDF」鎖死 🔒。
  3. 提示文字：「⚠️ 偵測到小數點。依法規台幣不可有角分，請將該發票**移出畫布**，或退回發票審核頁面修正來源資料為整數。」

### 4.4 發票恢復機制 (Recovery)
- 當使用者將發票拖入 Canvas 時，右側清單對應的 `jobId` 反灰 (Disabled)。
- **恢復解鎖**：當使用者在 Canvas 選取該發票並按下 `Delete` 鍵或右鍵「移除」時，觸發 `canvas.on('object:removed')` 事件，系統會將右側清單該 `jobId` 狀態重置，恢復為可拖曳。

### 4.5 二分搜尋排版演算法 (Auto-Layout Algorithm)
- **場景**：使用者在 Canvas 上亂放了 8 張發票，想要「一鍵整齊排列」。
- **參數說明**：
  - `N` = 畫布上的發票數量。
  - `H` = 所有發票調整後的**統一高度**。
  - `Max_width ≤ 535`：避免長條形發票 (如超商明細) 為了配合高度 `H`，其寬高比轉換出的寬度貫穿並超出安全區。
- **運作**：透過二分法尋找能在 `535x336` 安全區內，以「由左至右、滿了換行」規則剛好塞滿的最大 `H`。

### 4.6 300DPI 壓縮計算公式
- **佔比計算**：發票如果被縮放後，在 PDF 上佔用的物理尺寸為 `w_pts × h_pts`。
- **轉換公式**：
  - `Target Width (px) = (w_pts / 72) * 300`
  - `Target Height (px) = (h_pts / 72) * 300`
  - 例：放在 `200x150 pts` 的發票，後端會在貼上 PDF 前，先用 Pillow 調整大小成 `833x625 px`，最大化壓低產出檔案的容量。

### 4.7 快取機制更新 (@lru_cache Invalidations)
- `render_template_png` 會對底版 PDF 渲染做快取。
- 後端啟動時，會根據 `os.path.getmtime('backend/assets/憑證黏貼用紙.pdf')` 計算檔案的修改時間，並將其當作 Hash Key 的一部份傳入 Cache 函數。
- 若未來替換了新的 `憑證黏貼用紙.pdf` 實體檔案，`mtime` 改變，Cache 自動失效並重新渲染。

### 4.8 錯誤處理策略 (Error Handling)
1. **底模尺寸不符**：若是新版 PDF 尺寸不為 595×842，API 回傳 400，前端報錯「系統底模尺寸異常，請聯絡管理員」。
2. **圖片檔案損壞**：Pillow `Image.open` 發生 `UnidentifiedImageError`，後端略過該圖片，並將其在 PDF 該位置畫一個紅叉 ❌ `(Image Corrupted)` 避免中斷流程。
3. **網路中斷**：前端每 30 秒呼叫一次 `POST /layout` 自動存檔。若因斷網失敗，保存在 `localStorage`，下次重連時覆寫回 Server。

---

## 5. 多頁憑證處理邏輯 (Multi-Page Lifecycle)
1. **陣列結構**：前端 Vue state 擁有 `pages: [{ id: 1, images: [], fields: {} }]`。
2. **切換機制**：UI 會有橫向的分頁頁籤 (Tab 1, Tab 2, + 新增一頁)。
3. **Canvas 重繪**：點擊 Tab 2 時，執行 `canvas.clear()`，提取 `pages[1].images`，迴圈執行 `fabric.Image.fromURL` 將圖畫回畫布。
4. **數量上限**：無硬性上限，視待黏貼發票數量而定。

---

## 結語
本篇（v22）已完全解決 1~12 項的所有疑慮與實作盲區。架構、API、資料流已無歧義。
