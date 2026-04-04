# v0.0.13 實作計畫：JXL 全鏈路相容性（方案 A — 擴充 Adapter）

日期：2026-04-04

## 背景

v0.0.12 完成了 JXL 編碼器的切換與**前端預覽**修復，但後端管線中仍有大量元件直接使用 `cv2.imread` 或 `PIL.Image.open`，這些 API 無法讀取 JXL 檔案。

本版目標是透過最小侵入的方式，讓 **所有** 涉及圖片讀取的元件都能正確處理 JXL 來源。

---

## 策略

**擴充現有的 `ImageCodecAdapter`**，在其「寫入端」（已完成）旁邊補上「讀取端」（`read_image`、`read_image_pil`），使所有消費者可以透過統一入口讀寫圖片。

不新建模組，不改架構層級，改動量最小化。

---

## 損壞點清單

以下整理了現有程式碼中所有會因 JXL 來源而壞掉的地方：

| # | 檔案 | 行 | 問題 | 嚴重度 |
|---|------|----|------|-------|
| 1 | `file_ops.py` | L73 | `_prepare_tasks` 副檔名白名單缺 `.jxl`，JXL 原始圖無法進入分割流程 | 🔴 致命 |
| 2 | `file_ops.py` | L171-173 | `add_project_files` 的 codec 轉換白名單缺 `.jxl`，手動添加 JXL 圖會被當作「非圖片」直接 copy | 🔴 致命 |
| 3 | `voucher_generator.py` | L217 | `_image_stream_for_rect` 使用 `Image.open`，PIL 無法讀取 JXL | 🔴 致命 |
| 4 | `voucher_generator.py` | L318 | `generate_voucher_pdf` 使用 `fitz.Pixmap(path)`，PyMuPDF 不支援 JXL | 🔴 致命 |
| 5 | `voucher_generator.py` | L342 | `insert_image(filename=path)` 直接餵 JXL 路徑給 PyMuPDF | 🔴 致命 |
| 6 | `qr_handler.py` | L270 | `__main__` 區塊使用 `cv2.imread`，無法讀中文路徑JXL | 🟡 低（僅測試用） |
| 7 | `rapidocr_handler.py` | L270 | `__main__` 區塊使用 `cv2.imread`，同上 | 🟡 低（僅測試用） |
| 8 | `vision_handler.py` | L592 | `__main__` 區塊使用 `cv2.imread`，同上 | 🟡 低（僅測試用） |
| 9 | `utils.py` | L15 | `cv_imread_chinese` 使用 `cv2.imdecode`，對 JXL 回傳 None | 🔴 致命 |
| 10 | `voucher.py` (router) | L167-173 | `_load_image_bytes` 已有 JXL 分支但重複邏輯 | 🟢 已修（但有冗餘） |
| 11 | `file_ops.py` | L351-359 | `_render_preview` 已有 JXL 分支但重複邏輯 | 🟢 已修（但有冗餘） |

---

## 擬議變更

### 1. 擴充 ImageCodecAdapter — 加入讀取端

#### [修改] `backend/processing/image_codec_adapter.py`

新增：
```python
def read_image(self, path: str | Path) -> np.ndarray:
    """讀取任意格式的圖片，回傳 BGR numpy 陣列。"""
    path = Path(path)
    if path.suffix.lower() == ".jxl":
        import imagecodecs
        raw = path.read_bytes()
        arr = imagecodecs.jpegxl_decode(raw)  # RGB
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return cv_imread_chinese(str(path))

def read_image_pil(self, path: str | Path) -> Image.Image:
    """讀取任意格式的圖片，回傳 RGB 的 PIL.Image 物件。"""
    path = Path(path)
    if path.suffix.lower() == ".jxl":
        import imagecodecs
        raw = path.read_bytes()
        arr = imagecodecs.jpegxl_decode(raw)  # RGB
        return Image.fromarray(arr)
    return Image.open(str(path))
```

> 設計考量：這兩個方法未來加 HEIF 時，只需在此加一個 `elif` 分支。不需要動任何消費者。

---

### 2. 更新核心讀取工具

#### [修改] `backend/utils/utils.py`

- `cv_imread_chinese(filepath)` 加入 `.jxl` 偵測分支：
  - 若為 `.jxl`，使用 `imagecodecs.jpegxl_decode` → `cv2.cvtColor(RGB→BGR)` 回傳
  - 其他格式走原本的 `cv2.imdecode` 路徑

這是最基礎的修改，讓所有已經在用 `cv_imread_chinese` 的元件（`workers.py`、`file_ops.py`、`jxl_encoder_backend.py`）自動獲得 JXL 讀取能力。

---

### 3. 修復副檔名白名單

#### [修改] `backend/engine/file_ops.py`

- **L73**: `_prepare_tasks` 白名單加入 `.jxl`
  ```python
  # 修改前
  if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
  # 修改後
  if not image_name.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.jxl')):
  ```

- **L171-173**: `add_project_files` codec 轉換白名單加入 `.jxl`
  ```python
  # 修改前
  if original_suffix in ('.png', '.jpg', '.jpeg', '.bmp'):
  # 修改後
  if original_suffix in ('.png', '.jpg', '.jpeg', '.bmp', '.jxl'):
  ```

- **L347-361**: `_render_preview` 移除手動 JXL 分支，改用 `ImageCodecAdapter.read_image_pil()`

---

### 4. 修復憑證 PDF 產生器

#### [修改] `backend/engine/voucher_generator.py`

**`_image_stream_for_rect` (L216-227)**：
- `Image.open(image_path)` 改為 `ImageCodecAdapter().read_image_pil(image_path)`

**`generate_voucher_pdf` (L318 & L342)**：
- `fitz.Pixmap(img_path)` 改為先用 Adapter 讀取 PIL Image → 取得 width/height
- `insert_image(filename=img_path)` 改為 `insert_image(stream=jpeg_bytes)`（先轉為 JPEG bytes）

---

### 5. 清理 Voucher Router 重複邏輯

#### [修改] `backend/routers/voucher.py`

- `_load_image_bytes` (L166-183) 的手動 JXL 分支改為使用 `ImageCodecAdapter.read_image_pil()`

---

### 6. __main__ 區塊修復（低優先級）

#### [修改] `qr_handler.py`、`rapidocr_handler.py`、`vision_handler.py`

- 各自 `__main__` 中的 `cv2.imread` 改為 `cv_imread_chinese`
- 僅影響開發者手動測試，不影響線上流程

---

## 不需要修改的部分

| 檔案 | 原因 |
|------|------|
| `receipt_splitter.py` | 只接收 `np.ndarray`，不負責讀檔 |
| `receipt_processor.py` | 只接收 `np.ndarray`，不負責讀檔 |
| `archive_handler.py` | 使用 `os.walk` 走全目錄，不做格式過濾 |
| `workers.py` | 已使用 `cv_imread_chinese`，修好 utils 即自動修好 |
| `jxl_encoder_backend.py` | 已使用 `cv_imread_chinese`，同上 |

---

## 修改依賴順序

```
1. utils.py (底層修復)
     ↓
2. image_codec_adapter.py (加讀取 API)
     ↓
3. file_ops.py (白名單 + 消除重複)
4. voucher_generator.py (PDF 產生修復)
5. voucher.py (消除重複)
     ↓
6. __main__ 區塊 (低優先級)
     ↓
7. 測試
```

---

## 驗證計畫

### 自動化測試

1. 執行既有測試確保無回歸：
   ```
   micromamba run -n OCR_GA python -m pytest tests/ -x -q
   ```

2. 新增 `tests/test_image_codec_adapter_read.py`：
   - 測試 `read_image` 讀取 JXL 回傳正確 shape 與 dtype
   - 測試 `read_image_pil` 回傳 RGB PIL Image
   - 測試非 JXL 格式走原路徑
   - 測試 `cv_imread_chinese` 對 JXL 檔案的新分支

### 手動驗證

1. 使用已有 JXL 分割圖的專案，確認：
   - 前端預覽圖正常（已在 v0.0.12 修好，回歸檢查）
   - 「匯出憑證 PDF」可成功產生，圖片清晰無色偏
   - 「重新分割」可正確讀取 JXL 原始圖

---

## 風險與注意事項

| 風險 | 緩解措施 |
|------|---------|
| BGR/RGB 色彩空間混淆 | `read_image` 明確回傳 BGR（OpenCV 慣例），`read_image_pil` 明確回傳 RGB（PIL 慣例）。方法名稱本身就標示了色彩空間。 |
| `imagecodecs` 未安裝 | `cv_imread_chinese` 對 JXL 會 raise `ImportError`，與現行行為一致（讓呼叫端的 try/except 捕獲）。 |
| Adapter 是 stateful 物件 | `read_image` / `read_image_pil` 設計為無狀態方法，不依賴 `self.processing_settings`，可安全呼叫。 |

## 需要使用者審閱

> [!IMPORTANT]
> 此更新將中心化圖片載入邏輯。即使系統缺少 `imagecodecs`，JXL 支援會被禁用，但標準格式（JPG/PNG）仍能正常運作。我們的目標是讓 JXL 成為後端的「一等公民」。

## 審閱優化建議 (v0.0.13-opt)

為了避免 `utils` 與 `Adapter` 之間的邏輯重疊，實作時將採用以下架構：

1.  **`utils.cv_imread_chinese`**：負責底層 JXL Numpy (BGR) 的解碼實作。
2.  **`ImageCodecAdapter.read_image`**：僅作為統一入口，純粹轉發呼叫 `utils.cv_imread_chinese`。
3.  **`ImageCodecAdapter.read_image_pil`**：負責 JXL PIL (RGB) 的解碼實作（因系統目前尚無 PIL 的共用底層）。

這樣可以確保 Numpy 讀取邏輯的一致性，同時讓 `workers.py` 等直接使用 `utils` 的模組自動獲得支援。
