# 憑證黏貼編輯器 — 究極計畫 v29（Perfect Execution Spec）

## 版本定位

本版是 `v25~v28` 的**最終收斂版**：
- 保留 v27/v28 的 46 項核心防禦
- 吸收 v26 後段「5 大深層地雷修正」
- 清除所有 `TBD`、路徑與驗證歧義
- 補齊「可直接開工」所需的部署、測試、驗收、回滾策略

**目標：一次實作到位，不再二度確認。**

---

## 0) 範圍與非範圍

### In Scope
1. 建立獨立 Voucher Editor（前端頁面 + 後端 5 API）
2. 與發票審核流程解耦，只讀取 `status='done'` 發票
3. 支援多頁畫布、草稿保存、PDF 產生
4. 完整防呆：非法日期、小數金額、越權 jobId、圖片失效
5. 完整測試矩陣（Backend pytest + Frontend vitest）

### Out of Scope（本版不做）
1. 新增 RBAC 系統（沿用現有專案授權邏輯）
2. 重新設計發票審核頁 UX
3. OCR/VLM 模型替換
4. 自訂紙張尺寸（固定 A4：595×842 pts）

---

## 1) 名詞與狀態機

- Invoice/Receipt：發票原稿
- Template：`憑證黏貼用紙.pdf`
- Voucher：發票貼到底模後的最終輸出 PDF
- Page：單一 voucher 的物理分頁
- jobId：唯一發票識別，必須隸屬於 `project_id`

發票狀態：
`pending -> vlm_processed -> done -> rejected`

**Voucher Editor 只顯示 `done`。**

---

## 2) Repo 對齊與部署前置（硬規定）

## 2.1 檔案路徑（固定）

- 字型：`backend/assets/fonts/kaiu.ttf`
- 底模：`backend/assets/templates/憑證黏貼用紙.pdf`
- 草稿：`backend/data/projects/{project_id}/voucher_layout.json`

## 2.2 `config.json` 新增鍵

```json
{
  "voucher_settings": {
    "template_pdf_path": "backend/assets/templates/憑證黏貼用紙.pdf",
    "font_ttf_path": "backend/assets/fonts/kaiu.ttf",
    "layout_root": "backend/data/projects",
    "max_pages": 10,
    "autosave_interval_sec": 30,
    "thumb_max_width": 800
  }
}
```

## 2.3 字型部署

若 repo 無法納入字型檔，需在 README 明示：
- Windows：從 `C:\Windows\Fonts\kaiu.ttf` 複製
- 放入 `backend/assets/fonts/kaiu.ttf`
- 啟動時若缺檔，API 直接回 500 + 明確訊息

---

## 3) API 最終定稿（以 v28 為主，消歧義）

## 3.1 Endpoints

1. `GET /api/voucher/{project_id}/template`
   - 回傳底模 PNG(base64) + project meta + `status='done'` 發票
   - 後端先合併 `manual_json_text ?? vlm_result_json`，統一輸出 `invoice.result`

2. `GET /api/voucher/{project_id}/image/{job_id}?thumb=true|false`
   - 驗證 jobId 隸屬 project，否則 403
   - `thumb=true` 回 800px 縮圖；否則回原圖

3. `GET /api/voucher/{project_id}/layout`
   - 無檔案回空 layout（非 404）

4. `POST /api/voucher/{project_id}/layout`
   - **寬容 schema（Draft）**
   - 允許空字串、半成品、非法日期
   - 儲存採 atomic write

5. `POST /api/voucher/{project_id}/generate`
   - **嚴格 schema（Strict）**
   - 金額/日期/權限全檢查
   - 全部 jobId 二次驗權，不過即 403

## 3.2 錯誤格式（統一）

- 403：
```json
{ "error": "FORBIDDEN", "detail": "Contains unauthorized invoice jobId: {jobId}" }
```

- 422：
```json
{ "error": "VALIDATION_ERROR", "detail": "amount/payDate format invalid" }
```

- 500：
```json
{ "error": "INTERNAL_ERROR", "detail": "Voucher generation failed" }
```

---

## 4) Layout Payload（最終版）

```json
{
  "globalPrefix": "D-16",
  "startIndex": 1,
  "pages": [
    {
      "pageIndex": 0,
      "fields": {
        "voucherNo": "D-16-01~03",
        "budgetItem": "帶動組",
        "amount": "4607",
        "purpose": "餐費、茶水",
        "receiptCount": "3",
        "payDate": "2024-11-28",
        "isManuallyEdited": false
      },
      "images": [
        {
          "jobId": "550e8400-e29b-41d4-a716-446655440000",
          "x": 30,
          "y": 394,
          "w": 200,
          "h": 150
        }
      ]
    }
  ]
}
```

---

## 5) 畫布/底模座標（最終落點）

A4 固定：`595 × 842 pts`

### 5.1 禁區與安全區
- 表頭禁區：`(71,185) -> (524,320)`
- 簽章1禁區：`(112,340) -> (491,394)`
- 簽章2禁區：`(89,730) -> (507,804)`
- 可黏貼區：`(30,394) -> (565,730)`（535×336）

### 5.2 表頭欄位（取消 TBD，定稿）
- `budgetItem`：`Rect(78, 196, 255, 220)`
- `purpose`：`Rect(214, 248, 411, 328)`（寬 197、高 80）
- `amount` 七格基準：
  - `y = 232`
  - `x_list = [430, 446, 462, 478, 494, 510, 526]`
- `payDate`：`(436, 286)`（顯示 ROC：`113/11/28`）
- `receiptCount`：`(534, 286)`
- `voucherNo`：`Rect(78, 224, 255, 246)`

> 以上座標需以單一 golden sample 做 1 次對位校正；校正後即鎖定，不再漂移。

---

## 6) 46 防禦最終執行條款（合併 v26~v28）

> 保留 v28 的 46 條；本章只補「實作不可模糊」條件。

1. **Ghost Image Bleed 防護**：圖片 async callback 前必檢查 `activePageIndex` + `renderToken`。
2. **Permanent Disable 防護**：`invoiceUsageMap` 必須為 computed（從 `pages[].images[].jobId` 推導）。
3. **Auto-save 不鎖死**：`/layout` 與 `/generate` 分離 Draft/Strict schema。
4. **Insert Text 靜默截斷防護**：檢查 `insert_textbox()` 回傳，若截斷附加 `...(略)` 並記 warning log。
5. **反向膨脹禁止**：`target_px = min((w_pts/72)*300, original_pixel_width)`。
6. **雙重越權檢查**：Router 先查 project，Generator 再逐 jobId 查 ownership。
7. **日期雙層驗證**：Strict schema + renderer 內 defensive parse（避免空字串崩潰）。
8. **圖片遺失降級**：前端顯示 placeholder；後端於 PDF 原位畫紅叉與「圖片損壞無法載入」。

---

## 7) 前端實作規格（Vue + Fabric）

## 7.1 新增頁面
- `frontend/src/views/VoucherEditorView.vue`

## 7.2 狀態模型
- `activePageIndex`
- `renderToken`
- `pages[]`
- `globalPrefix`, `startIndex`
- computed:
  - `usedJobIds`
  - `invoiceUsageMap`
  - `hasInvalidDate`
  - `hasDecimalAmount`
  - `canGenerate = !hasInvalidDate && !hasDecimalAmount && !isSaving`

## 7.3 互動規則
- 拖放、縮放、移動全程邊界彈回
- 空頁可保留（不自動刪），但不給串號
- 切頁觸發 autosave（debounce）
- 每 30 秒 background autosave
- 用途手改後 `isManuallyEdited=true`，新發票進來先詢問是否覆蓋

---

## 8) 後端實作規格（FastAPI + PyMuPDF）

## 8.1 新增模組
- `backend/routers/voucher.py`
- `backend/engine/voucher_generator.py`
- `backend/models/voucher_payload.py`（Draft/Strict Pydantic）
- `backend/repositories/voucher_layout_repo.py`

## 8.2 Draft vs Strict

### Draft（for `/layout`）
- 欄位允許空字串
- 僅做結構與基本型別檢查

### Strict（for `/generate`）
- `amount`：必須數字、`<= 9999999`
- `payDate`：必須 ISO
- `receiptCount`：必須整數字串
- `images[].jobId`：不可空
- `images[].w/h`：`>0`

## 8.3 IO 與效能
- 模板渲染：`@lru_cache(path, mtime)`
- layout 儲存：`.tmp` -> `os.replace`
- PDF 儲存：`doc.save(deflate=True, garbage=4)`
- `fitz.open()` 一律 context manager

---

## 9) 安全規範（必達）

1. `project_id` sanitize（去除 `..`, `/`, `\\`）
2. 圖片代理與 PDF 生成均做 project ownership 驗證
3. 錯誤回應不吐 stack trace
4. log 留 server 端（warning/error 分級）
5. 任何越權嘗試固定回 403（不回 404 混淆）

---

## 10) 測試矩陣（最終驗收）

## 10.1 Backend（pytest）
1. `/template` manual 覆蓋 vlm
2. `/generate` amount = 10000000 -> 422
3. `/generate` 混入外專案 jobId -> 403 + 指定 body
4. `/layout` 空欄位 payload -> 200
5. `compress_images` 不放大低解析原圖
6. `payDate=""` 在 Strict -> 422；在 Draft -> 200
7. `insert_textbox` 截斷時記錄 warning 並附 `...(略)`

## 10.2 Frontend（vitest）
1. 非法日期 -> `Generate` disabled
2. 小數金額 -> `Generate` disabled
3. 移除異常發票後 -> disabled 解除
4. 刪整頁後清單 disabled 狀態恢復（computed 驗證）
5. 快速切頁不殘影（renderToken）

## 10.3 Integration
1. 完整流程：template -> 拖放 -> autosave -> generate
2. 圖片 404 時前端 placeholder + 後端 PDF 紅叉補位

---

## 11) 里程碑（可交付）

### Phase A（2-3 天）
- 後端 API 骨架 + payload schema + layout repo

### Phase B（3-4 天）
- 前端畫布 + 多頁 + 拖放 + autosave

### Phase C（3-4 天）
- PyMuPDF 生成器 + 字型 + 欄位落點 + 壓縮

### Phase D（2-3 天）
- 安全/邊界防禦 + 單元測試 + 整合測試

### Phase E（1 天）
- Golden sample 對位 + 文檔收斂 + 上線前檢查

---

## 12) Definition of Done（DoD）

以下條件全部成立才算完成：
1. 5 個 API 全通，錯誤格式一致
2. 前端可穩定拖放/切頁/自動儲存，無殘影
3. `generate` 產出 PDF 與畫面一致（WYSIWYG 可接受誤差 < 2pts）
4. 防禦用例（越權、空日期、小數、超額、404 圖）全通
5. 測試矩陣至少 15 個 case 全綠
6. README 補齊字型/底模部署步驟

---

## 13) 風險與回滾

### 風險
1. 字型缺檔導致文字寬度偏差
2. 舊資料 layout 結構與新 schema 不相容
3. 大量圖片導致前端記憶體壓力

### 回滾策略
1. 保留 `/layout` Draft 寬容解析，對舊資料做 best-effort 讀取
2. 新 API 掛在 `/api/voucher/*`，不影響既有 `/api/{project_id}/jobs/*`
3. 若 PDF 生成異常，可暫時退回舊流程 export（feature flag）

---

## 14) v29 結論

v29 已把 v25~v28 的規格衝突全部收斂為**可直接施工**版本：
- 路徑定了
- 座標定了
- Schema 分層定了
- 安全回應定了
- 測試與 DoD 定了

**狀態：✅ Ready for Execution（可以直接開工）**
