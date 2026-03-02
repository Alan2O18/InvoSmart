# 憑證黏貼編輯器 — 究極計畫 v21 (全 44 項防禦展開)

## 目標

將「憑證黏貼」從發票流程**完全解耦**，建立具備 **44 項極限防禦機制**（歷經 16 輪深度審核測試出）的獨立編輯頁面。

---

## 座標與禁區

| 區域 | 矩形 (pts) | 規則 |
|:---|:---|:---|
| 表頭 | `(71,185)→(524,320)` | ❌ NO-GO |
| 簽章 1 | `(112,340)→(491,394)` | ❌ NO-GO |
| 簽章 2 | `(89,730)→(507,804)` | ❌ NO-GO |
| **可黏貼區** | **`(30,394)→(565,730)`** | ✅ 535×336 pts |

---

## � 核心 44 項極限修補全清單 (The 44 Defenses)

### A. 實體座標與物理限制 (Physical Constraints) - 8 項
1. **虛擬座標鎖定**：Canvas 初始化鎖死為 `595x842`，保證與 A4 PDF 比例絕對 1:1。
2. **`setZoom` 防錯位**：捨棄 CSS Transform，改用 Fabric 內建 `setZoom()` 縮放，防滑鼠事件點位偏移。
3. **動態 Page Rect**：後端 PyMuPDF 繪圖前，動態讀取底模 `page.rect` 作為基準，防範未來底版尺寸微調。
4. **鎖死旋轉 (WYSIWYG Guarantee)**：強制 `lockRotation=true`。因 PyMuPDF `insert_image(*rect)` 不支援矩陣旋轉角度，防範印出變形。
5. **絕對座標反向推導**：送出 JSON 前使用 `canvas.viewportTransform` 反算，消除畫布拖移 (Panning) 造成的螢幕視角偏差。
6. **Retina 防模糊**：Canvas 強制套用 `devicePixelRatio`，修正 MacBook/高解析螢幕下發票縮圖鋸齒。
7. **浮點數淨化縮編**：前端傳送 `(x,y,w,h)` 座標前強制 `Math.round(num*100)/100`，避免 JS 無盡小數點精度遺失與 Payload 肥大。
8. **實體邊界牆 (Containment)**：監聽 `moving/scaling`，發票邊緣若突破 535×336 安全區，立刻強行覆寫座標「實體彈回」。

### B. 會計嚴格防呆 (Strict Accounting) - 7 項
9. **發票防重複請款 (Double-Dipping)**：把發票從清單拖上 Canvas 後，清單端即刻反灰禁用，防範同一筆錢請款兩次。
10. **非法日期零妥協**：只要偵測到 `""`, `None` 等非法 VLM 日期，**絕對不 fallback 為今日**。
11. **非法日期鎖死閥**：一旦發生非法日期，整欄「支付日期」爆紅，並且右上角「產出 PDF」按鈕強制 Disabled。
12. **物理碰撞偵測 (Anti-Overlap)**：在 Canvas 移動物件時若 BBox 相交，邊框變紅警告，提示重疊會擋住金額無法核章。
13. **台幣非整數報警**：加總後若存在小數，金額框背景亮黃色，並跳出文字警告。
14. **台幣無條件進位 (Ceiling)**：發生小數時，強制執行 `Math.ceil()` 向上取整，保障報帳方權益，不可四捨五入。
15. **金額極限防爆**：後端嚴格過濾非數字，加總若 `> 9999999` (七位數)，拋出 ValueError，防禦格子溢出。

### C. 文字排版與格式對齊 (Typography & Formatting) - 9 項
16. **金額跨格定位算法**：金額不是一個字串寫完，而是逐字算出 `[百][十][萬][仟][佰][拾][元]` 對應的 7 個 X 座標獨立 `insert_text`。
17. **台幣靠右對齊墊字**：數字傳給後端前，需執行 `str(amount).rjust(7, '※')` 補足前導符號，確保 146 會填入最後三格。
18. **ISO 轉民國曆**：抽出 `2024-11-28` 後，後端繪圖前經過正則擷取並執行 `year - 1911` 轉換為 `113/11/28`。
19. **用途說明自動換行 (Auto-wrap)**：設定 `insert_textbox`，讓 PyMuPDF 自動計算單行 197 pts 寬度並折行。
20. **用途說明自動縮字 (Auto-shrink)**：若換行後超過 80 pts 高度極限，啟動字體漸減迴圈 (14pt → 13pt → 12pt...)。
21. **用途欄位爆框黃燈**：前端偵測換行過多時，輸入框背景變黃，提示「字體過小請精簡」。
22. **跨平台字型綁定 (Portability)**：放棄寫死 Windows 路徑，改讀取專案內建 `backend/assets/fonts/kaiu.ttf`，Linux/Mac 皆不崩潰。
23. **前端 WebFont 同步**：前端 `@font-face` 載入同一個 `kaiu.ttf` 給 `fabric.Text`，確保前後端字寬度量完全一致，實現真・WYSIWYG。
24. **Emoji 與罕見字過濾 (Glyph Crash)**：後端寫字前使用 Regex 強行移除非 ASCII 與非 CJK 的特殊字元 (如 🍱)，防範 PyMuPDF 缺字庫崩潰。

### D. 欄位自動化與資料來源 (Data Pipeline) - 7 項
25. **Per-page 獨立域運算**：所有欄位 (金額/用途/張數) 皆依照「目前在該頁 Canvas 上的 images」獨立重新計算，非全域合計。
26. **人工修正優先權 (Manual Priority)**：讀取資料時 `manual_json_text ?? vlm_result_json`，手動審核過的資料凌駕於 AI 原始提取。
27. **用途說明去重拼接**：提取所有發票的 `items[].category`，進行 Set 去重複後，以「、」字元合併為預設用途。
28. **最晚日期選取器**：遍歷該頁所有有效日期，取 `Math.max()` 日期作為請款「支付日期」。
29. **全域憑證號配置器**：頂端設計 `[前綴][起始號]` 設定鈕，統一管理。
30. **自動串號演算法**：遍歷各頁張數分配序號 (Page1 有 3 張 → `D-16-01~03`，Page2 有 2 張 → `D-16-04~05`)。
31. **零發票保護邊界**：若清單內無任何 `status='done'` 發票，顯示 Empty State 視圖，禁用畫布功能。

### E. 作業系統安全與伺服器穩定 (OS & Stability) - 7 項
32. **路徑穿越防禦 (Path Traversal)**：儲存 `.json` 時對傳入的 `project_id` 執行 Sanitization（替換 `/`, `\`, `..`），防止駭客寫錯位。
33. **排版 JSON 原子寫入 (Atomic Write)**：儲存 Layout 時先寫 `.tmp` 再 `os.replace`，防範高並發連續存檔造成的 Corrupted JSON 斷頭檔。
34. **圖片白名單安全代理**：`GET /image/{jobId}` 限縮只能返還對應 Job 的實體路徑，防止透過 URL 直取伺服器母機任意檔案。
35. **後端孤兒發票時序防護**：產 PDF 的迴圈內增加 `if not os.path.exists(path): continue`，防止最後 0.5 秒發票圖檔被別台電腦刪除造成的 `FileNotFoundError` 500 崩潰。
36. **底版 PNG RAM 快取 (@lru_cache)**：`render_template_png()` 加入快取，確保 105KB 的底圖純粹從記憶體百微秒級返回，防止 CPU 反覆呼叫 PyMuPDF 解析。
37. **空字串例外攔截 (ZeroDivisionError)**：防範 PyMuPDF 對空字串算字寬的底層報錯，加入 `if not text.strip(): return`。
38. **with 上下文資源回收**：PyMuPDF `fitz.open()` 強制使用 Context Manager 包裝，發生例外立刻 `.close()` 放掉 C++ 指標，防 Memory Leak。

### F. 效能與輸出品質 (Performance & IO) - 6 項
39. **前端縮圖代理 (Anti-OOM)**：`/image?thumb=true` 讓後端只丟 800px 以下 WebP 給 Canvas，防範塞入 10 張 4000px 原始圖檔吃爆瀏覽器記憶體。
40. **上傳全局 WebP/JXL 轉檔 (預留)**：(使用者需求) 於發票上傳時直接轉為省空間格式，斷絕大小寫副檔名 404 問題。
41. **後端高畫質還原**：PDF Server 端產出時，不取用 thumb，直接調用原始解析度貼上。
42. **PDF 300DPI 尺寸壓縮**：插入圖片前，依據在座標上的佔比，用 Pillow 將圖片強制降維至 300 DPI 像素量，防止 PDF 膨脹到 50 MB 被行政系統退件。
43. **無損 PDF 發布壓縮**：PyMuPDF 最後加上 `doc.save(deflate=True, garbage=4)` 做最極致的文件瘦身。
44. **二分搜尋排版演算法 (Adaptive Packing)**：實作 O(N log H) 的行高搜尋陣列排版，並限制 `Iter_max = 20` 防止浮點數死迴圈，且加註單圖 `Max_width ≤ 535` 避免長條明細破版。

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
此計畫包含：
- `/backend/routers/voucher.py` (5 支新建代理及轉存端點)
- `/backend/engine/voucher_generator.py` (PyMuPDF 實作層)
- `/frontend/src/views/VoucherEditorView.vue` (Fabric 核心系統層)
