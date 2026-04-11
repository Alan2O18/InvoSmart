# v0.0.16 實作計畫：架構重構與技術債清理

日期：2026-04-10

---

## 背景與目標 (Background & Goals)

過去兩個版本（v0.0.14 與 v0.0.15）為系統引入了兩套大型功能：
1. **v0.0.14 手動二切與快取管理**：新增快取自動清理、背景 JXL 壓縮、手動 resub-rects 等機制。
2. **v0.0.15 印章管理系統**：全套的印章上傳、辨識、去背、儲存與 API。

然而，這些快速疊代導致了明顯的**模組臃腫 (Bloat)** 與 **技術債 (Tech Debt)**，使得程式碼變得「一坨」，特別是：
- `backend/engine/file_ops.py` (FileOps 類別) 已經膨脹到接近 900 行的「上帝物件 (God Object)」。
- 印章管理 (`stamps.py`) 實作了 raw DB Session 操作，打破了後端的 Repository Pattern 慣例。
- 太多職責被綁死在 Router 或 Engine 單一點上。

**v0.0.16 的核心目標為：不新增大型功能，專注於重構、解耦與測試覆蓋，穩定既有架構，為後續功能打下健康基礎。**

---

## 重構項目一：FileOps 解耦 (Decouple FileOps)

`FileOps` 目前包攬了原始檔案 I/O、影像旋轉變換、快取清理、JXL 壓縮與重新裁切，應拆分為多個具有單一職責的模組：

1. **`CacheManager` (`backend/engine/cache_manager.py`)**：
   - 負責縮圖預覽快取（AVIF/WebP/JPG）。
   - 負責 `ensure_preview_cache`, `invalidate_preview_cache`, `cleanup_project_cache` 功能。
2. **`JxlOptimizer` (`backend/engine/jxl_optimizer.py`)**：
   - 專門處理背景非同步的 JXL 圖片高壓縮（`optimize_jxl_storage`）。
   - 保留對於引擎 Semanphore 的感知。
3. **`ResplitManager` (`backend/engine/resplit_manager.py`)**：
   - 將「根據前端傳來的 4 個座標點進行手動二次裁切」 (`detect_job_sub_rects`, `apply_job_resplit`) 的邏輯拆離。
   - 保留矩陣投影轉換 `_warp_by_points` 等幾何數學處理。
4. **`FileOps`**：
   - 縮減為單純負責 `add_project_files`, `delete_job_files` 等真正的「實體資源新增與刪除」邏輯。

---

## 重構項目二：印章系統標準化 (Standardize Stamp System)

v0.0.15 中 `backend/routers/stamps.py` 內包含了大量的 `db.execute()`, `db.add()`, 等直接存取 SQLAlchemy 的操作。

1. **實作 Repository Pattern**：
   - 建立 `backend/repositories/stamp_repository.py` (`StampRepository` class)。
   - 擴充資料庫存取層，封裝 `list_stamps`, `create_stamps`, `delete_stamp`。
2. **重構 API 路由**：
   - 將 `routers/stamps.py` 淨化，只負責介面接收與回應組成。所有 DB 與業務邏輯委託給 `StampRepository`。
3. **優化預防措施**：
   - 確保刪除印章 DB 紀錄的同時，強保證硬體上的 `.png` 檔案被安全移除，並加入錯誤處理與日誌紀錄。

---

## 重構項目三：前端元件瘦身 (Frontend UI Cleanup)

1. 重視 `ResplitModal.vue` 與 `StampAssignDialog.vue` 中可能有重複 Canvas 繪圖與座標擷取邏輯。
2. 可考慮抽離出共用的 `ImageBoundingBoxEditor.vue`，專門處理【框選區域、拖拉變形、回傳座標】行為。
3. 清理已棄用的程式碼或沒用到的舊有狀態管理器 (Pinia store)。

---

## 預期執行步驟 (Execution Sequence)

1. **Phase 1: Backend Repository Refactoring** 
   - 實作 `StampRepository`。
   - 重構 `routers/stamps.py`。
   - 確認印章儲存與刪除的單元測試通過。
2. **Phase 2: Extracting Cache & Optimizer**
   - 建立 `cache_manager.py`、`jxl_optimizer.py`，從 `file_ops.py` 移植相對應的代碼。
   - 更新 `core.py` 上的匯入與引用路徑。
3. **Phase 3: Extracting Resplit**
   - 建立 `resplit_manager.py`，從 `file_ops.py` 移除透視校正等邏輯。
   - 執行全部測試 (`pytest`) 確保核心功能無毀損。
4. **Phase 4: Frontend Component Cleanup**
   - 檢查並重構 Vue 元件，抽離重複模組。

---

## 驗證計畫 (Verification Plan)

- [ ] **重構無感驗證**：既有的「手動二切」與「印章上傳儲存」功能不應有任何行為改變。
- [ ] **快取安全**：使用不同的快取生命週期測試 `CacheManager` 是否能正確清除。
- [ ] **單元測試**：新增至少涵蓋 `StampRepository` CRUD 邏輯的單元測試。
- [ ] 執行 `ruff check backend` 確認沒有代碼壞味道。
