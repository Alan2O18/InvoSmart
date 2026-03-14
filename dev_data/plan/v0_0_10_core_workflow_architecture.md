# AI Agent Lab — 全生命週期工作流核對書

本文件描述一個專案從**建立**到**交付所有行政文件**的完整生命週期。
輔助機制（建議詞迴圈、影像旋轉等）穿插在對應階段中，不再獨立成章。

---

## 全生命週期流程圖

```
建立專案 ──► 上傳原始檔案 ──► 轉檔(JXL) ──► 切分(大圖才需要)
                                                    │
                                                    ▼
                                            AI 辨識 (VLM)
                                                    │
                                          ┌─────────┴─────────┐
                                          ▼                   ▼
                                    辨識成功            辨識失敗/方向錯
                                          │                   │
                                          │            影像旋轉修正 ◄─┐
                                          │                   │       │
                                          │                   ▼       │
                                          │            重新送 VLM ────┘
                                          │
                                          ▼
                              產生前端快取圖 (AVIF/WebP)
                                          │
                                          ▼
                              人工修正 (Job Editor)
                              ├── 前端載入: 小圖 + JSON
                              ├── 使用者校對並修正欄位
                              ├── 儲存 → 回饋迴圈萃取建議詞
                              └── 確認無誤 → 標記 done
                                          │
                                          ▼
                              資料扁平化 (Flattening)
                              巢狀 items → 2D 關聯表
                                          │
                        ┌─────────────────┼─────────────────┐
                        ▼                 ▼                 ▼
                  報表產生             憑證黏貼紙         專案封存
                  (Excel/Word)        (Voucher PDF)     (Archive)
                        │                 │
                        ▼                 ▼
                  下載實體文件        前端排版(AVIF小圖)
                                          │
                                          ▼
                                   排版 JSON → 後端
                                          │
                                          ▼
                                   高清渲染(JXL原圖寫入PDF)
                                          │
                                          ▼
                                   PDF 壓縮
                                          │
                                          ▼
                                   下載憑證 PDF
```

---

## 階段 1：專案建立與前後文注入

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 1-1 | 使用者在前端填寫專案資訊 | 活動名稱、起訖日期、**預算科目群組 (group)** |
| 1-2 | 前端呼叫 `POST /api/projects` | 夾帶 `metadata` JSON + 原始檔案 |
| 1-3 | 後端建立專案目錄結構 | `原始輸入/`、`分割發票/` |
| 1-4 | 後端將 metadata 寫入 DB | `project.metadata.group` 後續自動映射至憑證的預算科目 |

---

## 階段 2：影像收錄與 AI 辨識

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 2-1 | 接收原始圖檔 | JPG / PNG / BMP |
| 2-2 | **轉檔 → JXL** | 壓縮體積但保留 600dpi 細節，供後續 VLM 辨識與 PDF 高清寫入 |
| 2-3a | **大圖** → 智慧切分 | `ReceiptSplitter.split()` 切出每張發票獨立存為 JXL |
| 2-3b | **小圖** → 跳過切分 | 單張發票直接存為 JXL |
| 2-4 | 送交 VLM 辨識 | OpenAI / Ollama Vision → 結構化 JSON |
| 2-5 | 建立 Job 進入佇列 | `engine.enqueue_job()` → 狀態 `pending` → `done` |

**輔助機制 — 影像旋轉**：若掃描方向顛倒，使用者可觸發 `POST /files/{id}/rotate/{filename}`，OpenCV 直接覆寫硬碟圖檔後重新送交 VLM。

---

## 階段 3：人工修正與資料壓平

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 3-1 | **產生前端快取圖** | 後端額外生成極小的 **AVIF / WebP** 縮圖 |
| 3-2 | 前端載入 Job Editor | 拉取 VLM JSON + AVIF 小圖，秒開不卡頓 |
| 3-3 | 使用者校對、修正欄位 | `amount`, `supplier_name`, `items[]` 等 |
| 3-4 | 儲存修正 | `PUT /jobs/{job_id}/json` → 寫回 DB |
| 3-5 | **建議詞反饋萃取** | 儲存時後端非同步攔截，將店名/品項寫入 `suggestions` 表 |
| 3-6 | 確認完成 → 狀態標記 `done` | |
| 3-7 | **資料扁平化 (Flattening)** | 將巢狀 `items` + `summary` 壓成 2D 關聯表，提早儲存備用 |

**輔助機制 — 建議詞迴圈**：步驟 3-5 萃取的資料會在下次前端輸入同欄位時，經由 `GET /suggestions?category=supplier&q=...` 提供自動完成下拉選單。

---

## 階段 4：報表產生

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 4-1 | 從 DB 撈出已壓平的資料集 | 不再即時壓平，直接使用階段 3 的產出 |
| 4-2a | 產生 **Excel (XLSX)** | `POST /{id}/run_export` → 經費核銷清單 |
| 4-2b | 產生 **Word (DOCX)** | `POST /{id}/run_word_export` → 讀取 `backend/assets/templates/報表範本.docx` (正規化位置)，Jinja2 替換 |
| 4-3 | 交付使用者 | 前端透過 FileResponse 下載 |

---

## 階段 5：憑證黏貼紙 (Voucher PDF)

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 5-1 | 前端載入排版編輯器 | 拉取模板 PNG + **AVIF 小圖** (輕量，拖拉順暢) |
| 5-2 | 使用者拖拉排版 | Fabric.js Canvas：拖拉發票位置 (x, y, scale) |
| 5-3 | 打回排版 JSON | `POST /voucher/{id}/generate` 含每頁 images + 文字欄位 |
| 5-4 | **後端高清渲染** | 從磁碟取出 **JXL 原圖**（非前端的 AVIF），寫入 PDF |
| 5-5 | 文字座標套用 | 讀取 `voucher_template_config.json` 動態配置 + 字體自動縮放 |
| 5-6 | **PDF 壓縮** | Ghostscript / pikepdf 壓縮，避免檔案過肥 |
| 5-7 | 交付使用者 | 壓縮後的 600dpi 高品質 PDF |

---

## 階段 6：專案封存 (Archive)

| 步驟 | 動作 | 技術細節 |
|------|------|----------|
| 6-1 | 使用者觸發封存 | `POST /{id}/run_archive` |
| 6-2 | 打包專案目錄 | 含原始輸入、分割發票、產出報表、憑證 PDF |
| 6-3 | 標記專案狀態為 `ARCHIVED` | 後續不可再修改 |

---

## ⚠️ 附錄：系統現況盤點與架構落差

| 理想狀態 | 實際現況 | 影響 |
|----------|----------|------|
| 上傳後轉存 JXL | `file_ops.py` 儲存為 `.jpg` (OpenCV) | PDF 品質尚可，但檔案體積未優化 |
| 前端拿 AVIF 小圖 | API 直接吐原始 JPG/PNG | 大圖拖拉卡頓 |
| PDF 壓縮後交付 | 尚未實作壓縮環節 | 憑證 PDF 檔案可能過大 |
| Word 範本在 `backend/assets/templates/` | 目前放在 `dev_data/空白 模板 (1).docx` | 路徑不規範 |
| 扁平化在人工修正後即時完成 | 目前在報表產出時才即時壓平 | 多次報表產出會重複計算 |

---

## 🚀 附錄：系統升級與遷移腳本需求 (Migration Scripts)

為了消弭上述存續的架構落差，並將舊有專案平滑過渡到新的全生命週期工作流，我們在執行 V0.0.10 (或 V0.0.11) 升級時，需配套開發以下獨立腳本來執行歷史資料清洗與轉換：

### 1. 影像格式雙軌升級腳本 (`scripts/migrate_images_to_jxl_avif.py`)
- **目的**：將舊專案儲存在 `原始輸入/` 與 `分割發票/` 中的 `.jpg` 與 `.png` 檔案，全面轉換為新的 JXL 與 AVIF 架構。
- **步驟**：
  1. 走訪 `backend/data/projects` 下的歷史專案資料夾。
  2. 讀取 `.jpg`，使用高畫質編碼生成對應的 `.jxl`（取代原檔）。
  3. 壓縮並縮放生成對應的 `.avif`（存入快取給前端使用）。
  4. 清理無用的舊 `.jpg` 檔案以釋放空間。

### 2. 資料庫扁平化結構遷移腳本 (`scripts/migrate_db_flatten_jobs.py`)
- **目的**：將資料庫中僅以巢狀 JSON (`items` array) 存在的舊 Job，提前跑一次壓平演算法。
- **步驟**：
  1. 針對 `global.db` 中狀態已為 `done` 的 Job 進行遍歷。
  2. 提取 `summary`、`items` 與 `project.metadata.group` 執行 Flatten 邏輯。
  3. 將結果寫回對應 Job 的新欄位 (如 `flattened_data`)，或寫入獨立的關聯表。

### 3. 資產路徑正規化搬遷腳本 (`scripts/migrate_assets_paths.sh`)
- **目的**：解決 Word 報表底稿放在開發用資料夾 (`dev_data`) 的不合規問題。
- **步驟**：
  1. 自動建立 `backend/assets/templates/` 目錄。
  2. 把 `dev_data/空白 模板 (1).docx` 搬動並重新命名為 `backend/assets/templates/報表範本.docx`。
  3. 同步修改 `run_word_export` Router 中硬編碼的路徑指向。
