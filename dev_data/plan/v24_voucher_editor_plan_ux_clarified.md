# 憑證黏貼編輯器 — 究極計畫 v24 (合併展開 + 深層 UX/Edge-Case 釐清)

## 目標

將「憑證黏貼」從發票流程**完全解耦**，建立獨立編輯頁面。本計畫合併了 v21 所有的「44 項極限防禦全展開」，並依照最新審核意見**無損追加**了詳細的 UX 情境表、前後端資料處理分工表，確保所有實作細節無任何歧義。

---

## 0. 詞彙表 (Glossary)
- **發票 (Invoice/Receipt)**：使用者上傳的各種消費單據原稿圖片。
- **底模 (Template)**：空白的系統表單（如 `憑證黏貼用紙.pdf`）。
- **憑證 (Voucher)**：將多張發票黏貼於**底模**之上，並填妥各項申報欄位後產出的最終 PDF 檔案。
- **頁面 (Page)**：一張憑證可能由多個物理分頁組成（例如 10 張發票需要 3 頁底模才能貼完）。

---

## 1. 資料流程圖 (Data Flow)

```mermaid
graph TD
    A[上傳發票圖片] --> B[VLM 辨識提取 JSON]
    B --> C[發票審核頁面 (人工審核/修正)]
    C --> D[進入獨立 Voucher Editor]
    D --> E[取得底模與發票選單 GET /template]
    E --> F[拖曳發票至 Canvas 黏貼]
    F --> G[左側即時計算金額/日期/用途]
    G --> H{偵測異常?<br>非法日期/小數}
    H -->|是| I[鎖定產出鈕<br>要求退回審核頁修改]
    H -->|否| J[POST /generate 產出憑證 PDF]
```

---

## 2. API 端點清單 (API Specifications)

| Method | Path | Request/Response 說明 |
|:---|:---|:---|
| `GET` | `/api/voucher/{project_id}/template` | **Res**: `{ templatePng: str(base64), projectMeta: dict, invoices: [ { jobId: str, imageUrl: str, vlmResult: dict... } ] }` |
| `GET` | `/api/voucher/image/{job_id}?thumb=true` | **Res**: 回傳 `image/webp` 縮圖或 JPEG 原圖 (Image Proxy) |
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

## 🔥 核心 44 項極限修補全清單 (The 44 Defenses)

### A. 實體座標與物理限制 (Physical Constraints) - 8 項
1. **虛擬座標鎖定**：Canvas 初始化鎖死為 `595x842`，保證與 A4 PDF 比例絕對 1:1。
2. **`setZoom` 防錯位**：捨棄 CSS Transform，改用 Fabric 內建 `setZoom()` 縮放，防滑鼠事件點位偏移。（預設初始 Fit-to-Viewport，允許滑鼠滾輪縮放，限制 0.5x ~ 2.0x）。
3. **動態 Page Rect**：後端 PyMuPDF 動態讀取底模 `page.rect`，防範未來底版尺寸微調。
4. **鎖死旋轉 (WYSIWYG Guarantee)**：強制 `lockRotation=true`，防範 PyMuPDF `insert_image` 失去旋轉矩陣導致拉伸變形。
5. **絕對座標反向推導**：送出 JSON 前使用 `canvas.viewportTransform` 反算，消除畫布 Panning 偏差。
6. **Retina 防模糊**：Canvas 強制套用 `devicePixelRatio`，修正高解析螢幕鋸齒。
7. **浮點數淨化縮編**：傳送座標前強制 `Math.round(num*100)/100`，避免 JS 小數點精度遺失 Payload 肥大。
8. **實體邊界牆 (Containment)**：發票邊緣若突破 535×336 安全區，立刻強行覆寫座標「彈回安全區」。

### B. 會計嚴格防呆 (Strict Accounting & Source Integrity) - 7 項
9. **發票防重複請款 (Disabled State)**：拖上 Canvas 後，清單端即刻反灰禁用。若從畫布刪除 (Delete/移除)，則**重新恢復可拖曳狀態**。
10. **非法日期零妥協**：偵測到 `""`, `None` 等非法日期，絕對不 fallback 為今日。（計算最晚日期時，忽略非法日期；若當頁*全為*非法，整欄爆紅等待修正）。
11. **源頭修正鎖死閥 (Date UX)**：若有非法日期，整欄爆紅且「產出 PDF」鎖死。提示「移除發票 或 退回審核頁修改來源」（移除是不想印這張，退回修改是想印但資料錯了）。
12. **物理碰撞偵測 (Anti-Overlap)**：BBox 相交時邊框變紅警告，防擋住金額與核章。但**不會鎖定產出**（保留使用者排版彈性），僅視覺提示。
13. **台幣非整數報警 (Decimal UX)**：加總若遇小數，金額框亮黃色且「產出 PDF」鎖死。提示退回審核頁修改。
14. **前端加總保護**：移除 Math.ceil() 短線修正，回歸「源頭錯誤源頭修」精神。
15. **金額極限防爆**：後端嚴格過濾 > 9999999 (七位數) 拋出 ValueError。

### C. 文字排版與格式對齊 (Typography & Formatting) - 9 項
16. **七位數精準定位**：金額對應 `[佰萬][拾萬][萬][仟][佰][拾][元]` 的 7 格座標獨立 `insert_text`。
17. **台幣靠右對齊墊字**：數字傳給後端前執行 `str(amount).rjust(7, '※')` 補足前導符號，確保 `146` 座落最後三格。
18. **ISO 轉民國曆**：後端繪圖前擷取 `YYYY` 執行 `year - 1911` 轉換為 `113/05/12`。
19. **用途說明自動換行 (Auto-wrap)**：設定 `insert_textbox`，單行寬 197 pts 滿了折行。
20. **用途說明自動縮字 (Auto-shrink)**：換行超過 80 pts 極限，啟動字體漸減迴圈 (14pt降至12pt...)。
21. **用途欄位爆框黃燈**：前端偵測文字過長，輸入框背景變黃，提示字體過小。
22. **跨平台字型綁定**：讀取專案內建 `backend/assets/fonts/kaiu.ttf` (標楷體)，防路徑死機。
23. **前端 WebFont 同步**：前端 `@font-face` 載入同一個 `kaiu.ttf`，字元寬度度量完全一致，落實 WYSIWYG。
24. **Emoji 缺字過濾 (Glyph Crash)**：後端寫字前用 Regex 移除非 ASCII 與非 CJK 的特殊字元 (如 🍱)，防 PyMuPDF 崩潰。

### D. 欄位自動化與資料來源 (Data Pipeline) - 7 項
25. **Per-page 獨立域運算**：所有欄位 (金額/用途/張數) 皆依照「該頁面上目前放置的 images」獨立重新計算。
26. **人工修正優先權 (Manual Priority)**：讀取資料時 `manual_json_text ?? vlm_result_json`，以發票審核頁面的人工資料為準。
27. **用途說明去重拼接**：只要拖入或移除發票（觸發計算），便提取當頁發票 `items[].category` 去重拼接為預設用途。若手動覆寫則以手動為準。空值顯示空白。
28. **最晚日期選取器**：遍歷該頁有效日期，取 `Math.max()` 寫入「支付日期」。
29. **全域憑證號配置器**：頂端設計 `[前綴][起始號]` 設定鈕。
30. **自動串號演算法**：遍歷各頁自動產生憑證號。單張顯示 `D-16-04`，多張顯示 `D-16-01~03`。
31. **發票清單篩選邊界**：`/template` API 的 `invoices` 陣列，僅包含當前 Project 內且 `status='done'` 的發票。如果清單為空，顯示 Empty State 並禁用畫布功能。

### E. 伺服器安全與穩定 (OS & Stability) - 7 項
32. **路徑穿越防禦 (Path Traversal)**：儲存時對 `project_id` 執行 Sanitation（替換 `/`, `\`），防寫錯位。底模位置為 `backend/assets/憑證黏貼用紙.pdf`；Layout 位置為 `backend/data/projects/{project_id}/voucher_layout.json`。
33. **排版 JSON 原子寫入 (Atomic Write)**：儲存 Layout 時先寫 `.tmp` 再 `os.replace`，防範高並發被截斷成 Corrupted JSON。
34. **圖片跨專案白名單代理**：`/image/{jobId}` 除了還原 Job 實體路徑，更會驗證該 Job 是否屬於當前操作使用者的專案，否則回傳 403 Forbidden。
35. **後端孤兒發票時序防護**：產 PDF 時增加 `if not os.path.exists(path): continue`，防最後一秒圖檔被刪引發 `FileNotFoundError` 500 崩潰。
36. **API 回應錯誤遮罩設計**：API 全面 Try-Catch 攔截給予合理回饋。
37. **空字串例外攔截 (ZeroDivisionError)**：防 PyMuPDF 對空字串算字寬報錯，加入 `if not text.strip(): return`。
38. **with 上下文資源回收**：`fitz.open()` 強制使用 Context Manager 包裝，發生例外自動 `.close()`，防 Memory Leak。

### F. 效能與輸出品質 (Performance & IO) - 6 項
39. **前端縮圖代理 (Anti-OOM)**：`/image?thumb=true` 只回傳 800px 縮圖給 Canvas，防吃爆記憶體。
40. **上傳全局格式轉檔 (預留)**：上傳發票轉為 WebP/JXL 省空間。
41. **後端高畫質還原**：PDF Server 端直接調用高畫質原圖貼上。
42. **PDF 300DPI 尺寸壓縮**：插入圖片前，依據點陣佔比強制縮放為 300 DPI 像素量。計算公式：`target_px = (w_pts / 595) * (A4_width_inch * 300)`。防止檔案膨脹被退件。
43. **無損 PDF 發布壓縮**：PyMuPDF 寫入時加上 `doc.save(deflate=True, garbage=4)` 做極致瘦身。
44. **二分搜尋 O(N log H) (自動排版)**：使用者點擊「自動排版」按鈕時觸發（非拖放時觸發）。O(N log H) 的 N=畫面上的發票數量，H=發票統一高度。`Max_width ≤ 535` 確保即使高度算好，超長明細的寬度也不會穿出安全區。

---

## 🎯 補強附錄 (增補規格)

### A. 使用者操作情境表 (UX Interaction Scenarios)
| 情境 | 系統行為 |
|:---|:---|
| **拖入發票從清單至畫布** | 發票放置於滑鼠放下點 (Drop Position)。清單上該項目立刻反灰 (Disabled)，左側面板重新計算該頁總金額、最晚日期與用途拼接。 |
| **從畫布刪除發票 (Delete/移除)** | 從畫布移除物件。右側發票清單該項目恢復可選色 (Enabled)，重新計算該頁總金額、最晚日期與用途拼接。 |
| **切換憑證頁面 (Tab)** | 儲存當前頁 Canvas State (存入記憶體)，呼叫 `canvas.clear()`，從 Array 抽出目標頁資料，重新載入目標頁 images 與文字至畫布，重算側邊欄。 |
| **偵測到非法/無效日期** | 當前頁面的「支付日期」欄位字體爆紅。右上角「產出 PDF」按鈕強制Disabled。<br>提示：*「偵測到無效日期。請將異常發票移出畫布，或退回發票審核頁面修正來源資料。」* |
| **偵測到小數點金額** | 當前頁面的「總金額/支付金額」欄位背景變黃 🟡。右上角「產出 PDF」按鈕強制Disabled。<br>提示：*「依法規台幣不可有角分。請退回發票審核頁面修正來源資料為整數。」* |
| **發票在畫布上重疊** | 發票的 BBox 邊框變為紅色以示警告，提示使用者可能會遮擋印出內容。但不鎖定產出鈕（允許使用者刻意推疊）。 |
| **「自動排版」按鈕點擊** | 觸發第44項二分搜尋演算法，將畫布上所有零散發票整齊由左至右、換列疊放。 |

### B. 前後端資料處理分工表 (Data Processing Division)
| 欄位 / 功能 | 前端 (Vue) 送出欄位型態 | 後端 (FastAPI/PyMuPDF) 接收處理邏輯 |
|:---|:---|:---|
| **`amount` (總金額)** | **純數字字串** `"4607"` | 執行 `rjust(7, '※')` 變為 `"※※※4607"`，轉換 7 格座標逐字寫入。 |
| **`payDate` (支付日期)** | **ISO 字串** `"2024-11-28"` | 正則解析，算術 `-1911`，轉換並字串拼接成民國百年曆格式 `"113/11/28"` 繪製。 |
| **`purpose` (用途說明)** | **拼接後文字** `"餐費、茶水"` | 交由 PyMuPDF 執行 Auto-wrap (換列) 與 Auto-shrink (縮字)、字元過濾。 |
| **`receiptCount`** | **純數字字串** `"3"` | (代表該頁畫布上實體黏貼的發票數量)。後端直接列印。 |
| **發票座標 `(x,y,w,h)`**| **純數字浮點數** `145.25` | 直接作為 `fitz.Rect` 參數插入圖片，或作為 300DPI 計算依據。 |

### C. 全面錯誤處理清單 (Comprehensive Error Handling)
| 錯誤情境 | HTTP Status | 系統行為與提示訊息 |
|:---|:---|:---|
| **底模檔案損壞/不存在** (`憑證黏貼用紙.pdf` 遺失) | `500 Internal Server Error` | Backend 記錄 Error Log。前端 Snackbar 提示：「系統底模遺失或損毀，請聯絡系統管理員修復環境。」 |
| **單一發票圖片損壞** (`UnidentifiedImageError`) | `200 OK` (不中斷產出) | 後端 `generate_pdf` 只會略過該發票不貼上，或在原座標畫個紅 X，但仍會產生 PDF 來提醒使用者檔案已損壞。 |
| **總金額超越七位數上限** | `422 Unprocessable Entity` | PDF 拒絕生成。前端提示：「總金額不可超過 999 萬 9999 元，請拆分請款憑證。」 |
| **非法操作不屬於本人的發票/專案** | `403 Forbidden` / `404` | 該使用者嘗試代理非自己專案的 `jobId` 圖片，立刻阻擋並回傳 403。 |

### D. 多頁管理操作細節 (Pagination Limits)
- **新增頁面**：點擊 Tab 列的 `[+] 新增憑證頁` 手動新增一頁空白底板。
- **頁數上限**：暫限制最多 `10` 頁。
- **空白頁儲存與產出**：空頁面可以正常儲存 Layout，**但後端產出時會自動略過完全沒有任何 Images 的頁面**，避免印出廢紙。
- **刪頁補號**：刪除頁面後，剩餘的 `pages[]` 陣列自動重排索引 (Index)，左側的**憑證編號**（如 `D-16-01~03`）會基於各頁的 `receiptCount` 即時聯動刷新重新串號。
