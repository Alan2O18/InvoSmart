# 憑證黏貼編輯器 — 究極計畫 v23 (合併展開與嚴格 UX 版)

## 目標

將「憑證黏貼」從發票流程**完全解耦**，建立獨立編輯頁面。本計畫合併了 v21 的「44 項極限防禦全展開」與 v22 的「架構規格書」，並修正了無效憑證的 UX 流程，確保 100% 遵守會計資料源頭管理準則。

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

## 4. 關鍵演算法與機制解說

### 4.1 二分搜尋排版演算法 (Auto-Layout Algorithm)
透過二分法尋找能在 `535x336` 安全區內，以「由左至右、滿了換行」規則剛好塞滿發票的最大統一高度 `H`。並以 `Max_width ≤ 535` 限制長條形發票破版。

### 4.2 300DPI 壓縮計算公式
若發票在 Canvas 上的佔用尺寸為 `w_pts × h_pts`。
轉換公式：`Target Width (px) = (w_pts / 72) * 300`。
PyMuPDF 貼上前，Pillow 會先將圖縮小至 Target 解析度。

### 4.3 底模 PNG 快取機制 (@lru_cache)
後端 `render_template_png` 會對 PDF 解析做快取，並將實體檔案修改時間 `os.path.getmtime()` 當作 Cache Key。若底模檔案遭替換，快取自動失效重繪。

### 4.4 多頁憑證處理邏輯 (Multi-Page Lifecycle)
Vue state 擁有 `pages[]` 陣列。介面上以頁籤 (Tabs) 切換。點擊切換頁面時，Canvas 先 `clear()`，再迴圈載入目標分頁的所有 `fabric.Image`，且產出時送出完整陣列。

---

## 🔥 核心 44 項極限修補全清單 (The 44 Defenses)

### A. 實體座標與物理限制 (Physical Constraints) - 8 項
1. **虛擬座標鎖定**：Canvas 初始化鎖死為 `595x842`，保證與 A4 PDF 比例絕對 1:1。
2. **`setZoom` 防錯位**：捨棄 CSS Transform，改用 Fabric 內建 `setZoom()` 縮放，防滑鼠事件點位偏移。
3. **動態 Page Rect**：後端 PyMuPDF 動態讀取底模 `page.rect`，防範未來底版尺寸微調。
4. **鎖死旋轉 (WYSIWYG Guarantee)**：強制 `lockRotation=true`，防範 PyMuPDF `insert_image` 失去旋轉矩陣導致拉伸變形。
5. **絕對座標反向推導**：送出 JSON 前使用 `canvas.viewportTransform` 反算，消除畫布 Panning 偏差。
6. **Retina 防模糊**：Canvas 強制套用 `devicePixelRatio`，修正高解析螢幕鋸齒。
7. **浮點數淨化縮編**：傳送座標前強制 `Math.round(num*100)/100`，避免 JS 小數點精度遺失 Payload 肥大。
8. **實體邊界牆 (Containment)**：發票邊緣若突破 535×336 安全區，立刻強行覆寫座標「彈回安全區」。

### B. 會計嚴格防呆 (Strict Accounting & Source Integrity) - 7 項
9. **發票防重複請款 (Disabled State)**：拖上 Canvas 後，清單端即刻反灰禁用。若從畫布刪除 (Delete/移除)，則**重新恢復可拖曳狀態**。
10. **非法日期零妥協**：偵測到 `""`, `None` 等非法日期，絕對不 fallback 為今日。
11. **源頭修正鎖死閥 (Date UX)**：若有非法日期，整欄爆紅且「產出 PDF」鎖死。提示：*「⚠️ 偵測到無效日期。請將異常發票從畫布移除，或退回發票審核頁面修正來源資料。」* **(禁止本地 Override)**。
12. **物理碰撞偵測 (Anti-Overlap)**：BBox 相交時邊框變紅警告，防擋住金額與核章。
13. **台幣非整數報警 (Decimal UX)**：加總若遇小數，金額框亮黃色且「產出 PDF」鎖死。提示：*「⚠️ 依法規台幣不可有角分。請退回審核頁面修正，或移除該發票。」* **(不擅自套用進位)**。
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
27. **用途說明去重拼接**：提取當頁發票 `items[].category` 去重複後以「、」合併為預設用途。
28. **最晚日期選取器**：遍歷該頁有效日期，取 `Math.max()` 寫入「支付日期」。
29. **全域憑證號配置器**：頂端設計 `[前綴][起始號]` 設定鈕。
30. **自動串號演算法**：遍歷各頁自動累加序號 (`D-16-01~03`, `D-16-04`)。
31. **零發票保護邊界**：清單若無 `status='done'` 項目，顯示 Empty State 並禁用畫布。

### E. 伺服器安全與穩定 (OS & Stability) - 7 項
32. **路徑穿越防禦 (Path Traversal)**：儲存時對 `project_id` 執行 Sanitation（替換 `/`, `\`），防寫錯位。
33. **排版 JSON 原子寫入 (Atomic Write)**：儲存 Layout 時先寫 `.tmp` 再 `os.replace`，防範高並發被截斷成 Corrupted JSON。
34. **圖片白名單安全代理**：`/image/{jobId}` 查詢只還原對應 Job 實體路徑，防止直取伺服器任意檔。
35. **後端孤兒發票時序防護**：產 PDF 時增加 `if not os.path.exists(path): continue`，防最後一秒圖檔被刪引發 `FileNotFoundError` 500 崩潰。
36. **API 回應錯誤遮罩設計**：API 全面 Try-Catch 攔截 500 給予合理回饋。
37. **空字串例外攔截 (ZeroDivisionError)**：防 PyMuPDF 對空字串算字寬報錯，加入 `if not text.strip(): return`。
38. **with 上下文資源回收**：`fitz.open()` 強制使用 Context Manager 包裝，發生例外自動 `.close()`，防 Memory Leak。

### F. 效能與輸出品質 (Performance & IO) - 6 項
39. **前端縮圖代理 (Anti-OOM)**：`/image?thumb=true` 只回傳 800px 縮圖給 Canvas，防吃爆記憶體。
40. **上傳全局格式轉檔 (預留)**：上傳發票轉為 WebP/JXL 省空間。
41. **後端高畫質還原**：PDF Server 端直接調用高畫質原圖貼上。
42. **PDF 300DPI 尺寸壓縮**：插入圖片前，依據點陣佔比強制縮放為 300 DPI 像素量，防止檔案膨脹被系統退件。
43. **無損 PDF 發布壓縮**：PyMuPDF 寫入時加上 `doc.save(deflate=True, garbage=4)` 做極致瘦身。
44. **二分搜尋 O(N log H)**：實作高度最佳化分配演算法，配以 `Iter_max = 20` 避免無窮迴圈。

---

## Payload Data Structure

```json
{
  "globalPrefix": "D-16",
  "startIndex": 1,
  "pages": [{
    "fields": { "voucherNo": "D-16-01~03", "budgetItem": "帶動組",
                "amount": "4607", "purpose": "餐費、茶水",
                "receiptCount": "3", "payDate": "114/11/28" },
    "images": [{ "jobId": "j1", "x": 30, "y": 394, "w": 200, "h": 150 }]
  }]
}
```

## 開發路徑指示
- `/backend/routers/voucher.py` (新建 5 支端點)
- `/backend/engine/voucher_generator.py` (PyMuPDF 實作層，防護 A、C、E、F)
- `/frontend/src/views/VoucherEditorView.vue` (Fabric 選單/排版層，防護 A、B、C、D、F)
