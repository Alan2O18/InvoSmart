# v0.0.14 實作計畫：儲存空間清理 & 手動二切工具

日期：2026-04-04

---

## 背景

本版本聚焦於三個領域：

1. **磁碟空間清理**：解決快取影像遺留（尤其是 Windows 檔案鎖定造成的殘留）與刪除 Job 時沒有同步清除實體檔案的問題。
2. **JXL 儲存優化**：預設使用無損壓縮 (`lossless=True`)。對現有 JXL 透過背景高壓縮 (`effort=7`) 進一步縮小體積，像素完全不變。
3. **手動二切工具（Re-splitting）**：當自動裁切結果不理想（多張票沾黏成一張），使用者可透過互動介面「看著框框修」後，系統再次裁切並產出正確的 Jobs。

---

## 功能一：快取影像自動清理

### 問題描述

`快取影像/voucher_preview/` 資料夾可能遺留以下情況的舊快取：
- 圖片被**旋轉**後，舊簽名的快取無法在 Windows 上刪除（`WinError 32`，StaticFiles 持有鎖定）。
- Job 被刪除後，快取沒有同步清除。

### 解決方案

**啟動時掃描清理**：每次後端啟動時，對所有專案的快取資料夾進行一次全域掃描，刪除無效快取。

### 快取檔名格式

```
{stem}_{mtime_ns}_{size}_{max_width}.{avif|webp|jpg}
```

清理規則：
1. **原始圖不存在**：`分割發票/` 中找不到任何與 `stem` 相符的檔案 → 刪除快取。
2. **簽名不符**：原始圖的 `mtime_ns` 或 `size` 與快取檔名中的簽名不符 → 刪除快取。

### 設計注意事項

> [!WARNING]
> `stem` 本身可能包含底線（如 `A_split_0_1234567890`），因此解析時必須**從後往前**取出 3 個 `_` 分隔的 segment 作為簽名，其餘的才是 stem。

---

## 功能二：Job 刪除同步清除檔案

### 問題描述

前端刪除 Job（`DELETE /api/projects/{pid}/jobs/{jid}`）後：
- 只刪除資料庫記錄。
- `分割發票/` 中的 JXL/AVIF 等實體圖檔仍然存在。
- `快取影像/` 中的預覽縮圖也仍然存在。

### 解決方案

修改 `Engine.delete_job`，在刪除 DB 記錄之前：
1. 從 DB 讀取該 Job 的 `image_path` 與 `preview_cache_path`。
2. 呼叫 `FileOps.delete_job_files(project_id, image_path, preview_cache_path)` 刪除實體檔案。
3. 若刪除失敗則記錄 warning，**不影響 DB 刪除**（讓後續啟動清理收拾殘局）。

---

## 功能三：JXL 背景高壓縮

### 問題描述

JXL 預設即採用 **無損壓縮 (`lossless=True`)**。目前編碼時暫用 `effort=1`（追求寫入速度）。發票圖片在辨識完成後，不需要再追求寫入速度，可在背景以更高的 `effort=7` 重新編碼以節省空間。

### 解決方案

**新增 `effort` 參數**至 `encode_image_to_jxl` 和 `encode_to_jxl`（目前寫死 `effort=1`）：

```python
# 現況
encoded = imagecodecs.jpegxl_encode(image_rgb, effort=1)

# 修改後：新增 lossless 與 effort 參數
def encode_image_to_jxl(image, output_path, lossless=False, effort=1):
    encoded = imagecodecs.jpegxl_encode(image_rgb, lossless=lossless, effort=effort)
```

**背景任務 `optimize_jxl_storage(project_id)`**：
1. 遍歷 `分割發票/` 中所有 `.jxl` 檔案。
2. 解碼 → 以 `lossless=True, effort=7` 重新編碼至暫存檔（**像素完全不變**）。
3. **只有**新檔比舊檔更小時才替換（`tmp.unlink()` 或 `rename`）。
4. 主圖像素完全不變（無損壓縮），**不需要**重建快取。
5. 整個流程使用 `asyncio.to_thread` 跑在背景，不阻塞主 event loop。

**觸發時機**：後端 `lifespan` 啟動後，以 `asyncio.create_task` 非同步啟動，低優先級執行。

> [!NOTE]
> 若 JXL 文件正被 StaticFiles 讀取（Windows 鎖定），`unlink` 會失敗並 `continue`，不影響其他檔案。

---

## 功能四：移除垂直旋轉偵測

### 問題描述

`perspective_transform.py` 的 `fix_orientation()` 對每張裁切結果做：
1. 灰階轉換
2. Otsu 二值化
3. 水平/垂直投影變異數計算
4. 若偵測到「垂直文字排列」，旋轉 90 度

這對真實發票幾乎**沒有效果**（拍攝已大致正向），反而拖慢每張圖的處理時間。

### 解決方案

**直接將 `fix_orientation` 改為直通函式（pass-through）**：

```python
def fix_orientation(image: np.ndarray) -> np.ndarray:
    """方向校正（v0.0.14 起已停用自動 90° 旋轉）"""
    return image
```

> [!NOTE]
> 「旋轉」功能已有專門的手動旋轉 API（`rotate_image`），使用者可自行決定，不需要自動猜測。

---

## 功能五：互動式手動二切工具（Re-splitting）

這是本版本最複雜的功能，分為**後端 API** 與**前端互動介面**兩部分。

### 整體流程

```
[前端] 點擊「手動二切」
    ↓
[後端] detect_job_sub_rects(project_id, job_id)
    → ReceiptSplitter 跑偵測（不裁切）→ 回傳建議座標 JSON
    ↓
[前端] 燈箱顯示圖片 + 建議框框（四點可拖拉，可新增/刪除框）
    ↓
[使用者] 調整框框到滿意
    ↓
[前端] 送出最終座標 → [後端] apply_job_resplit(project_id, job_id, final_rects)
    → 裁切 + 寫檔 + 建立新 Jobs + 刪除舊 Job（含實體圖檔）
```

### 後端 API 設計

#### API 1：取得建議切分座標

```
POST /api/projects/{project_id}/jobs/{job_id}/detect-sub-rects
Response:
{
  "image_w": 1200,
  "image_h": 800,
  "rects": [
    {"id": 0, "pts": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]},
    {"id": 1, "pts": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]}
  ]
}
```

實作細節：
- 呼叫 `ReceiptSplitter.detect_only(image)` → **新增**此方法，只跑到取得 `final_rects` 為止，把 `(center, size, angle)` 格式的 `minAreaRect` 轉換成 4 點座標後回傳，**不執行裁切**。
- 回傳座標為**相對於該 Job 圖片的像素座標**。

#### API 2：執行裁切

```
POST /api/projects/{project_id}/jobs/{job_id}/apply-resplit
Body:
{
  "rects": [
    {"pts": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]},
    {"pts": [[x0,y0],[x1,y1],[x2,y2],[x3,y3]]}
  ]
}
Response:
{
  "status": "resplit_completed",
  "new_job_ids": ["job-xxx", "job-yyy"],
  "deleted_job_id": "job-original"
}
```

實作細節：
- 接收 4 點座標（允許任意四邊形，不僅限矩形，方便傾斜的票）。
- 使用 `crop_by_rect` 的邏輯進行透視校正裁切。
- 依序建立新的 Job + 預熱快取 + 加入辨識佇列。
- 刪除原始 Job 及其**實體圖檔**（呼叫 `delete_job_files`）。

> [!IMPORTANT]
> 「全部分割」的流程（`run_splitting`）完全獨立，它只從「原始輸入」掃描並分割 → 不觸碰已在「分割發票」中的圖片。「二切」只由使用者在特定 Job 上手動觸發。

### 前端 UI 設計（Vue 元件）

#### 新增元件：`ResplitModal.vue`

**開啟方式**：在 Job 卡片或 Job 詳情頁增加「細切」或「手動二切」按鈕。

**Modal 內容**：
```
┌──────────────────────────────┐
│  手動二切                  [X]│
│                              │
│  [圖片預覽區域]              │
│  ├ 藍色邊框 = 偵測到的框框    │
│  └ 每個框框的 4 個角可拖拉    │
│                              │
│  [+ 新增框框]  [刪除選取]    │
│                              │
│  [取消]          [確認裁切]  │
└──────────────────────────────┘
```

**技術選型**：
- 使用 `<canvas>` 或 CSS `transform` 繪製並允許拖拉四點。
- 框框資料結構：`{ id, pts: [[x,y],[x,y],[x,y],[x,y]], color }`
- 確認後將 pts 換算回實際圖片像素座標（需考慮縮放比例）再送出。

---

## 改動檔案清單

### Backend

| 檔案 | 動作 | 說明 |
|------|------|------|
| `backend/processing/perspective_transform.py` | MODIFY | 移除 `fix_orientation` 的旋轉邏輯 |
| `backend/processing/jxl_encoder_backend.py` | MODIFY | `encode_image_to_jxl` 新增 `effort` 參數 |
| `backend/processing/receipt_splitter.py` | MODIFY | 新增 `detect_only()` 方法，只偵測不裁切 |
| `backend/engine/file_ops.py` | MODIFY | 新增 `cleanup_project_cache`、`delete_job_files`、`optimize_jxl_storage`、`detect_job_sub_rects`、`apply_job_resplit` |
| `backend/engine/core.py` | MODIFY | 修改 `delete_job`（加入檔案清理）；新增 `cleanup_all_caches`、`optimize_all_jxl`、`detect_sub_rects`、`apply_resplit` |
| `backend/routers/jobs.py` | MODIFY | 新增 `POST /{job_id}/detect-sub-rects` 與 `POST /{job_id}/apply-resplit` 兩個端點 |
| `backend/main.py` | MODIFY | Lifespan 加入啟動時清理任務與背景 JXL 優化任務 |

### Frontend

| 檔案 | 動作 | 說明 |
|------|------|------|
| `frontend/src/components/ResplitModal.vue` | NEW | 互動式四點框選 + 確認裁切 |
| `frontend/src/views/ProjectDetailView.vue` | MODIFY | Job 卡片上新增「細切」按鈕 |
| `frontend/src/api/jobs.js` | MODIFY | 新增 `detectSubRects`、`applyResplit` API 函式 |

---

## 修改依賴順序

```
1. jxl_encoder_backend.py (新增 effort 參數)
     ↓
2. perspective_transform.py (移除旋轉邏輯)
3. receipt_splitter.py (新增 detect_only 方法)
     ↓
4. file_ops.py (新增 5 個方法)
     ↓
5. core.py (修改 delete_job，新增 4 個方法)
     ↓
6. routers/jobs.py (新增 2 個端點)
7. main.py (lifespan 掛載任務)
     ↓
8. Frontend: api/jobs.js → ResplitModal.vue → ProjectDetailView.vue
```

---

## 驗證計畫

### 後端驗證

1. **快取清理**：
   - 旋轉一張圖片後關閉後端。
   - 確認舊快取仍存在（Windows 鎖定）。
   - 重啟後端，確認啟動時清理掉舊快取。
   
2. **同步刪除**：
   - 從前端刪除一個 Job。
   - 確認 `分割發票/` 中對應的 `.jxl` 與快取都被刪除。

3. **JXL 優化**：
   - 在 `optimize_jxl_storage` 執行前後比較檔案大小（應變小或不變）。
   - 解碼優化前後的檔案，逐像素比對確認完全相同（`lossless=True` 保證）。

4. **二切 API**：
   - `detect-sub-rects` 能正確回傳多個建議座標。
   - `apply-resplit` 能正確裁切並產出新 Jobs，舊 Job 被刪除。

### 前端驗證

1. 點擊「細切」開啟 Modal，圖片正常顯示，偵測框框正常繪製。
2. 拖拉四個頂點，框框跟隨移動。
3. 新增框框，座標能正確被新增到清單。
4. 按下「確認裁切」後，Job 列表更新（舊 Job 消失，新 Job 出現）。
