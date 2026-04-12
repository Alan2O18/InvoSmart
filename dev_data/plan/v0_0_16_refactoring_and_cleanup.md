# v0.0.16 實作計畫：全面架構重構與技術債大掃除

日期：2026-04-12 (決策整併版 v4)

---

## 背景與目標

過去兩個版本（v0.0.14 與 v0.0.15）為系統引入了兩套大型功能，但開發過程中因為趕工，導致了嚴重的模組臃腫 (Bloat) 與技術債 (Tech Debt)，使得程式碼品質下降。

**v0.0.16 的核心目標為：不新增大型功能，專注於建立標準、重構解耦、防呆機制與死碼清除，徹底降低未來的技術債堆積速度。**

> 本版已整併 2026-04-12 決策：
> - Processing Layer 不允許檔案 I/O
> - `delete_job_files` 改為延遲垃圾回收（非立即刪檔）
> - async 路徑要求全面非阻塞（可慢，不可堵塞 Event Loop）
> - FileOps 500 行限制允許 v0.0.16 過渡例外，v0.0.17 專項拆除

### 四大目標

| # | 目標 | 內容 |
|---|------|------|
| 1 | **建立標準技術選型標竿** | 統一前端繪圖技術、後端影像處理套件、非同步模式 |
| 2 | **建立 AI 防呆 Skill** | 新增 `.agent/skills/nknu-vlm-guard/SKILL.md` 防止未來亂改架構 |
| 3 | **建立標準多級模組架構** | 導入 Router → Service → Repository 三層式架構 |
| 4 | **剷除無用/無效/相容性代碼** | 清除死碼、重複 pattern、殘留註解 |

---

## 目標一：建立標準技術選型標竿

### 1.1 前端繪圖技術標準

| 場景 | 選定技術 | 說明 |
|------|---------|------|
| 複雜 2D 物件操作（拖放、縮放、背景圖） | **Fabric.js Canvas** | `VoucherEditorView`、`VoucherTemplateConfigView` |
| 簡單矩形框選/切換 | **原生 HTML/CSS DOM overlay** | `StampAssignDialog` 維持現狀 |
| 多邊形頂點拖拉 | **SVG overlay** | `ResplitModal` 維持現狀 |

> **決策**：四個繪圖元件使用三種不同技術，各自適合不同場景，**不強制統一**，但**禁止在同一元件內混用多種繪圖技術**。
>
> **決策**：**不建立 `useFabricCanvas.js` composable**。經審查，`VoucherEditorView` 與 `VoucherTemplateConfigView` 的 Fabric.js 使用方式差異極大（多物件排版 vs 錨點拖拉），能共用的僅有 `new Canvas()` / `dispose()` 兩行，不值得為此建立抽象層。

### 1.2 後端影像處理技術標準

| 場景 | 選定技術 | 禁止 |
|------|---------|------|
| 影像讀取/旋轉/裁切/編碼 | **OpenCV (`cv2`)** | 禁止使用 `PIL` 做同類操作 |
| 預覽快取縮圖生成 | **`PIL` (Pillow)** | 允許（因 AVIF/WebP 輸出 PIL 支援最好） |
| JXL 編碼/解碼 | **`jxlpy` via `ImageCodecAdapter`** | 禁止繞過 adapter 直接呼叫 |
| PDF 頁面渲染 | **`PyMuPDF (fitz)`** | 僅在 `add_pdf_files` 使用 |

### 1.3 非同步模式標準

| 場景 | 模式 | 說明 |
|------|------|------|
| CPU 密集 (影像處理) | `asyncio.to_thread()` | 推入執行緒池 |
| I/O 密集 (DB 查詢) | `async/await` 原生 | SQLAlchemy AsyncSession |
| 長時間背景任務 (VLM) | Worker Thread + Queue | 現有 `global_receipt_worker_loop` |
| 檔案系統 I/O (copy/move/unlink/mkdir/stat/glob...) | `asyncio.to_thread()` 或背景 Worker | **禁止**在 async 函數中直接呼叫同步 I/O |

> **🐛 發現 Bug：全後端 Event Loop 阻塞（影響範圍比預期更大）**
> 經全面掃描，阻塞問題不僅限於 `file_ops.py`，還存在於以下位置：
> - `file_ops.py`：`add_project_files` 的 `shutil.copy`、`_prepare_tasks` 的 `cv_imread_chinese` + `receipt_splitter.split`
> - `voucher.py`：`_load_image_bytes()` 同步圖片解碼/縮放、`generate_from_layout()` 同步 PDF 渲染
> - `groups.py`：`glob()` + `stat()` 目錄遍歷、`shutil.rmtree()` 遞迴刪除、`open().write()` 檔案寫入
> - `voucher.py`：`save_template_layout` 同步 JSON 讀寫
>
> 本版必須全面修復，不能只修 `file_ops.py`。

> **決策補充（2026-04-12）**
> 可接受 CPU 打滿導致回應變慢，但不可接受 Event Loop 被同步 I/O 阻塞。所有 async 函式中的檔案系統操作與 CPU 密集操作都必須改為 `asyncio.to_thread()` 或背景 worker。

### 1.4 Semaphore 使用標準

目前 `file_ops.py` 中有 **6 處**完全相同的 semaphore null-check 模式（L160, L293, L458, L644, L769, L867），導致大量重複代碼。

**名詞說明（Semaphore Scope）**：指 semaphore 控制的併發粒度（全域 / 每專案 / 每任務）。

**本版決策**：v0.0.16 採「進程級全域 semaphore（單一共享）」，限制同時進入重 I/O / 影像處理 `to_thread` 區塊的工作數，避免 thread 爆量與記憶體尖峰；更細分的每專案配額延後至 v0.0.17 評估。

**標準化方案**：建立 async context manager（不使用高階函數，避免參數傳遞災難）：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def _optional_semaphore(self):
    """若存在 semaphore 則 acquire，否則直接 yield。"""
    sem = self._image_semaphore()
    if sem is not None:
        async with sem:
            yield
    else:
        yield
```

原本每處 ~7 行改為 ~3 行，6 處合計省 ~24 行，且不需要拆函數或傳參數：
```python
# Before (每處重複)
semaphore = self._image_semaphore()
if semaphore is not None:
    async with semaphore:
        result = await asyncio.to_thread(func, ...)
else:
    result = await asyncio.to_thread(func, ...)

# After
async with self._optional_semaphore():
    result = await asyncio.to_thread(func, ...)
```

---

## 目標二：建立 AI 防呆 Skill

### 2.1 新增檔案

**[NEW] `.agent/skills/nknu-vlm-guard/SKILL.md`**

此 Skill 被安裝到 agent 環境中，任何 AI 助手修改此專案架構時，必須先閱讀此 Skill。

### 2.2 規則內容

```
1. Router Layer (backend/routers/*)
   - 只處理 HTTP 請求/回應、參數驗證、錯誤轉換
   - 禁止超過 20 行的業務邏輯
   - 禁止直接 import cv2 / numpy（影像處理屬於 Processing Layer）
   - 禁止直接操作 db.add() / db.execute()，必須委託 Repository

2. Service / Engine Layer (backend/engine/*)
   - 負責流程編排（調度多個 Repository 和 Processor）
    - 原則上每個 class 不得超過 500 行
    - v0.0.16 過渡例外：`FileOps` 可暫至 ~550 行，v0.0.17 必須專項拆除
    - 若超過且無例外，則拆分為 Mixin 或獨立 Service

3. Processing Layer (backend/processing/*)
   - 純影像處理、AI 推論、文字辨識
   - 無狀態，不得持有 DB Session
   - 輸入 numpy array，輸出 numpy array 或結構化結果

4. Repository Layer (backend/repositories/*)
   - 只負責 DB CRUD
   - 禁止寫業務邏輯（如影像處理、檔案 I/O）
   - 所有資料表都必須有對應的 Repository

5. 通用禁令
   - 禁止建立超過 800 行的單一檔案
   - 新功能必須附帶至少 1 個單元測試
```

---

## 目標三：建立標準多級模組架構

### 3.1 `file_ops.py` 瘦身 — Mixin 提取法（過渡方案）

經深度審查，`file_ops.py` 的 6 大方法互相依賴 cache/codec/engine，暴力拆成獨立模組會造成循環引用。因此本版本採用 **Mixin 提取法** 作為過渡方案。

> **注意**：Mixin 本質上是「假解耦」——方法依然共享同一個 `self`。這是有意為之的技術折衷。**v0.0.17 計畫將 FileOps 全面重構為獨立的 Service 層（CacheService / ImageService / FileService），實現真正的組合注入。**

#### 3.1.1 [NEW] `backend/engine/cache_mixin.py` (~200 行)

從 `file_ops.py` 提取以下方法：

| 方法名 | 原始行數 | 說明 |
|--------|---------|------|
| `_get_preview_cache_dir` | L394-398 | 獲取快取目錄 |
| `_get_preview_format` | L400-422 | Pillow 格式協商 |
| `_build_preview_cache_path` | L424-428 | 建立快取路徑 |
| `_render_preview` | L430-445 | 靜態方法：生成縮圖 |
| `ensure_preview_cache` | L447-476 | 確保預覽快取存在 |
| `invalidate_preview_cache` | L478-485 | 清除特定檔案快取 |
| `cleanup_project_cache` | L487-520 | 清理單一專案過期快取 |
| `cleanup_all_projects_cache` | L522-539 | 清理所有專案過期快取 |
| `_optional_semaphore` | (新增) | Async context manager，統一 semaphore 操作 |

**繼承方式**：`class FileOps(CacheMixin):`，Mixin 透過 `self.project_repo`、`self._engine_config()` 等存取宿主屬性。

#### 3.1.2 [MODIFY] `backend/engine/file_ops.py`

- 繼承 `CacheMixin`
- 使用 `async with self._optional_semaphore():` 替換 6 處重複 semaphore 代碼
- **修復 Bug（Event Loop 阻塞）**：`add_project_files`、`delete_job_files` 及其呼叫鏈中的同步檔案 I/O（`copy/move/unlink/mkdir/stat/exists/glob`）全部改為 `asyncio.to_thread()` 或背景 worker
- **修復 Bug（_prepare_tasks 阻塞）**：`_prepare_tasks` L162 的 `cv_imread_chinese` 和 `receipt_splitter.split` 是 CPU 密集型同步操作，在 semaphore 區塊內但沒有用 `to_thread` 包裝，必須修復
- **修復 Bug（Dangling Pointer 誤刪）**：`delete_job_files` 改為「延遲垃圾回收」：先刪 DB 關聯、寫入 GC 任務，再由 GC worker 二次檢查「仍無任何 Job 引用」後才刪除實體檔案
- **淨效果**：~900 行 → ~550 行

#### 3.1.3 `backend/engine/core.py` — 不修改

`FileOps` 的外部 API 不變，`core.py` 的所有 delegate wrapper 保持原樣。

### 3.2 印章系統標準化 — 貫徹三層架構

> **決策**：建立 `StampRepository`，不留破窗。雖然目前只有極簡 CRUD，但統一標準的價值遠大於省 50 行的開銷。
>
> **決策（2026-04-12）**：Processing Layer 不允許檔案 I/O。印章流程改由 Service/Engine 編排。

#### 3.2.1 [NEW] `backend/repositories/stamp_repository.py` (~50 行)

```python
class StampRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def list_stamps(self) -> list[dict]: ...
    async def create_stamps(self, entities: list[Stamp]) -> list[dict]: ...
    async def get_stamp(self, stamp_id: int) -> dict | None: ...
    async def delete_stamp(self, stamp_id: int) -> bool: ...
```

**回傳策略**：Repository 內部可使用 ORM entity，但對外統一回傳 DTO（dict 或 dataclass），避免 Session 關閉後物件狀態不一致、序列化隱性查詢與跨層耦合。

#### 3.2.2 [MODIFY] `backend/processing/stamp_processor.py`

新增純處理方法 `extract_stamps()`，只做「裁切→去背→回傳影像資料」，不做存檔、不碰 DB：

```python
def extract_stamps(
    self, image: np.ndarray, selections: list[dict], mode: str
) -> list[dict]:
    """
    Returns: [{image: np.ndarray, name, category, group_name}, ...]
    """
```

#### 3.2.3 [NEW] `backend/engine/stamp_service.py` (~120 行)

新增 `StampService` 作為流程編排層：

```python
class StampService:
    async def register_stamps(...):
        # 1) decode upload
        # 2) 呼叫 processor.extract_stamps
        # 3) 以 asyncio.to_thread() 寫檔
        # 4) 呼叫 StampRepository 落庫
        # 5) 回傳 API DTO
```

#### 3.2.4 [MODIFY] `backend/routers/stamps.py`

- 移除 `get_stamp_db()` 方法（改用 `backend/dependencies.py` 的 `get_db`）
- 移除 Router 內影像解碼與影像處理細節（委託 `StampService`）
- 移除直接 `db.execute()` / `db.add()` 操作，改委託 `StampRepository`
- `register_stamps` endpoint 瘦身 ~80 行
- Router 只做：**解析 Request → 呼叫 Service → 回 Response**
- 統一錯誤轉換：`404/409/422/500`

### 3.3 Voucher 系統修復

#### 3.3.1 [MODIFY] `backend/engine/voucher_generator.py`

- **🐛 修復記憶體外洩**：`generate_voucher_pdf` 方法的 `fitz.open()` 和 `fitz.Document()` 沒有用 `with` 語法。若處理圖片時拋異常，`.close()` 永遠不會被執行，PyMuPDF 底層 C/C++ 記憶體無法被 GC 回收。改為 `with fitz.open(...) as doc:` 確保釋放。
  （注意：`generate_from_layout` 已正確使用 `with`，僅 `generate_voucher_pdf` 有此問題）

#### 3.3.2 [MODIFY] `backend/routers/voucher.py`

- **🐛 修復 HTTP 狀態碼**：L293 `get_voucher_image` 在 Job 不存在時回傳 403 FORBIDDEN，應改為 404 NOT FOUND
- **🐛 修復 Event Loop 阻塞**：L307 `_load_image_bytes()` 同步影像解碼/縮放，包進 `asyncio.to_thread()`
- **🐛 修復 Event Loop 阻塞**：L389 `generate_from_layout()` 同步 PDF 渲染（可能要數秒），包進 `asyncio.to_thread()`
- **修復同步 JSON I/O**：L206-217 `save_template_layout` 的 `open()` + `json.load()` + `json.dump()` 包進 `asyncio.to_thread()`

### 3.4 Groups 系統修復

#### 3.4.1 [MODIFY] `backend/routers/groups.py`

- **🐛 修復 Event Loop 阻塞**：L65 `stamp_dir.glob("*")` + `p.stat()` 同步目錄遍歷，需包進 `asyncio.to_thread()`
- **🐛 修復 Event Loop 阻塞**：L109, L123 `shutil.rmtree()` 同步遞迴刪除，需包進 `asyncio.to_thread()`
- **🐛 修復 Event Loop 阻塞**：L155-156 `open(dest_path, "wb").write()` 同步寫入，需包進 `asyncio.to_thread()`

### 3.5 Dependencies 修復

#### 3.5.1 [MODIFY] `backend/dependencies.py`

- **🐛 修復 Null 檢查**：`get_db()` L66-69 直接呼叫 `AsyncSessionLocal()` 但沒有檢查 `AsyncSessionLocal is None`。若 DB 未初始化會拋 `TypeError` 而非乾淨的 503。諷刺的是，要被砍掉的 `stamps.py` 的 `get_stamp_db()` 反而有做這個檢查。修復方式：加入 `if AsyncSessionLocal is None: raise HTTPException(503)`

### 3.6 前端元件清理

> **決策**：不建立 `useFabricCanvas.js` composable。兩個 Fabric.js View 差異太大，強行抽象不划算。本版只做刪除死碼。

---

## 目標四：剷除無用/無效/相容性代碼

### 4.1 後端 Bug 修復總表

| # | 檔案 | 問題 | 嚴重性 | 行動 |
|---|------|------|--------|------|
| 1 | `file_ops.py` 6 處 | semaphore null-check 重複 | 中 | `_optional_semaphore` context manager |
| 2 | `file_ops.py` `add_project_files` | 🐛 `shutil.copy` 阻塞 Event Loop | **高** | 改 `asyncio.to_thread()` |
| 3 | `file_ops.py` `_prepare_tasks` | 🐛 `cv_imread` + `split` 阻塞 Event Loop | **高** | 改 `asyncio.to_thread()` |
| 4 | `file_ops.py` `delete_job_files` | 🐛 立即刪檔有誤刪與競態風險 | **高** | 延遲垃圾回收 |
| 5 | `voucher_generator.py` L301-354 | 🐛 PyMuPDF `fitz.open()` 未用 `with`，異常時記憶體外洩 | **高** | 改用 context manager |
| 6 | `voucher.py` L293 | 🐛 Job 不存在時回傳 403 應為 404 | 低 | 改狀態碼 |
| 7 | `voucher.py` L307 | 🐛 `_load_image_bytes()` 同步解碼阻塞 | **高** | 改 `asyncio.to_thread()` |
| 8 | `voucher.py` L389 | 🐛 `generate_from_layout()` 同步 PDF 渲染阻塞 | **高** | 改 `asyncio.to_thread()` |
| 9 | `voucher.py` L206-217 | 同步 JSON 讀寫阻塞 | 中 | 改 `asyncio.to_thread()` |
| 10 | `groups.py` L65, L109, L123, L155 | 🐛 glob/rmtree/write 阻塞 Event Loop | **高** | 改 `asyncio.to_thread()` |
| 11 | `dependencies.py` L66-69 | 🐛 `get_db()` 缺少 `AsyncSessionLocal is None` 檢查 | 中 | 加 503 守衛 |
| 12 | `core.py` L229 | `"Bug 1 fix"` 殘留註解 | 低 | 改為正式 docstring |
| 13 | `core.py` L443 | `"Bug 1 fix"` 殘留註解 | 低 | 同上 |
| 14 | `routers/stamps.py` L38-42 | 自建 `get_stamp_db()` 重複 | 低 | 刪除 |

### 4.2 後端死碼清除

| 檔案 | 問題 | 行動 |
|------|------|------|
| `perspective_transform.py` L107-121 | `fix_orientation()` 是 no-op（v0.0.14 已停用），但 `file_ops.py` L763 仍呼叫 | 刪除函數，移除 `file_ops.py` 中的呼叫 |
| `suggestions.py` L6 + L24 | `SuggestionRepository` import 重複兩次 | 刪除 L24 的重複 import |
| `suggestions.py` L7-8 | `get_engine` 和 `Engine` import 但從未使用 | 刪除未使用 import |

### 4.3 前端死碼清除

| 檔案 | 問題 | 行動 |
|------|------|------|
| `frontend/src/components/HelloWorld.vue` | Vite 腳手架殘留，從未使用 | **刪除**，並確認無殘留 import |

### 4.4 代碼品質掃描

- 執行 `ruff check backend --select F401` 清除未使用 import
- 執行 `ruff check backend` 全面檢查

### 4.4 CI 架構守門（新增）

- 新增 CI 檢查：`backend/routers/*` 禁止 `import cv2` / `import numpy`
- 新增 CI 檢查：`backend/routers/*` 禁止直接 `db.execute()` / `db.add()`
- 新增 CI 檢查：單一檔案超過 800 行直接 fail
- 將 `ruff check backend`、`pytest`、前端 `npm run build` 納入必跑 gate

---

## 執行順序 (Execution Sequence)

### Phase 1: 建規立法 (Standards & Guards)

- [ ] 建立 `.agent/skills/nknu-vlm-guard/SKILL.md`（AI 防呆 Skill）
- [ ] 建立 CI 架構守門腳本（Router import/db 禁令 + 單檔行數上限）

### Phase 2: 後端架構重構與 Bug 修復 (Backend Refactoring & Bug Fixes)

**file_ops.py 瘦身與修復：**
- [ ] 建立 `backend/engine/cache_mixin.py`（含 `_optional_semaphore`）
- [ ] 修改 `backend/engine/file_ops.py`：繼承 Mixin + 替換 6 處 semaphore 重複
- [ ] 🐛 修復 `file_ops.py`：`add_project_files` 的 `shutil.copy` 阻塞
- [ ] 🐛 修復 `file_ops.py`：`_prepare_tasks` 的 `cv_imread` + `split` 阻塞
- [ ] 🐛 修復 `file_ops.py`：`delete_job_files` 的 Dangling Pointer 誤刪
- [ ] 💀 移除 `fix_orientation()` 呼叫（L763），刪除 `perspective_transform.py` 的 no-op 函數

**印章系統三層分離：**
- [ ] 建立 `backend/repositories/stamp_repository.py`
- [ ] 修改 `backend/processing/stamp_processor.py`：新增純處理 `extract_stamps()`
- [ ] 建立 `backend/engine/stamp_service.py`：流程編排
- [ ] 修改 `backend/routers/stamps.py`：委託 Service + Repository

**Voucher 系統修復：**
- [ ] 🐛 修復 `voucher_generator.py`：`generate_voucher_pdf` 的 PyMuPDF 記憶體外洩
- [ ] 🐛 修復 `voucher.py`：`get_voucher_image` 錯誤狀態碼 403→404
- [ ] 🐛 修復 `voucher.py`：`_load_image_bytes` 與 `generate_from_layout` 阻塞 Event Loop
- [ ] 修復 `voucher.py`：`save_template_layout` 同步 JSON I/O

**Groups 系統修復：**
- [ ] 🐛 修復 `groups.py`：`glob/stat/rmtree/write` 阻塞 Event Loop（4 處）

**基礎設施修復：**
- [ ] 🐛 修復 `dependencies.py`：`get_db()` 加入 `AsyncSessionLocal is None` 的 503 守衛
- [ ] 清除 `core.py` 的殘留 `Bug fix` 註解
- [ ] 清除 `stamps.py` 的重複 `get_stamp_db()`
- [ ] 清除 `suggestions.py` 的重複 import 和未使用 import

### Phase 3: 前端清理 (Frontend Cleanup)

- [ ] 刪除 `components/HelloWorld.vue`

### Phase 4: 全面品質掃描 (Quality Sweep)

- [ ] 執行 `ruff check backend --select F401` 清除未使用 import
- [ ] 執行 `ruff check backend` 全面檢查代碼品質
- [ ] 執行 `pytest` 確認所有測試通過
- [ ] 補整合測試：延遲垃圾回收與非阻塞驗證
- [ ] 執行前端 `npm run build` 並確認零 warning
- [ ] 修改已壞的 mock 路徑（如有）

### Phase 5: 文件收斂 (Docs Finalization)

- [ ] 撰寫 `docs/architecture_manifesto.md`（以已落地實作為準回填）

---

## 驗證計畫 (Verification Plan)

- [ ] **重構無感驗證**：既有「手動二切」與「印章上傳儲存」功能行為不變
- [ ] **快取安全**：`CacheMixin` 提取後，preview cache 建立與清除邏輯正常
- [ ] **單元測試**：
  - 修改 `tests/test_engine_file_ops.py`，確認 Mixin 移植後 mock 路徑不壞
  - 新增 `tests/test_stamp_repository.py`，覆蓋 `StampRepository` CRUD
    - 新增 `tests/test_stamp_processor_extract.py`，覆蓋 `extract_stamps()` 純處理
- [ ] **整合測試**：
    - 新增 `tests/test_file_gc_deferred_cleanup.py`，覆蓋「同圖多 Job」延遲 GC 不誤刪
    - 新增 `tests/test_non_blocking_file_ops.py`，覆蓋大量檔案操作期間其他 API 仍可回應
- [ ] **Lint 檢查**：`ruff check backend` 零錯誤
- [ ] **CI 守門**：Router 禁令與單檔行數檢查通過
- [ ] 前端 `npm run build` 通過零 warning

---

## 技術債延後清單 (Deferred to v0.0.17)

以下項目已確認為技術債，但因風險或範圍限制，延後至 v0.0.17：

| 項目 | 說明 |
|------|------|
| FileOps 完全 Service 化 | 將 Mixin 升級為獨立的 `CacheService` / `FileService`，使用組合注入取代繼承 |
| Engine Facade 瘦身 | 減少 `core.py` 的 delegate wrapper，讓 Router 直接引用 Service |
| 前端 `VoucherEditorView` 瘦身 | 審查 `canvasLoadState` 定時器等 hack 是否可用 `watchEffect` 取代 |
