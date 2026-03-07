# 文件系統全面同步計畫 — Beta 0.0.3 (文件對齊與修補)

**日期**: 2026-03-07
**狀態**: 施工中（已審閱校正）
**前提**: 專案經歷了從傳統 OCR 遷移至 VLM-First 架構，以及「憑證黏貼編輯器 (Voucher Editor)」從無到有的複雜演進。目前 `docs/` 目錄部分文件已落後於程式碼現況，必須進行一次全面的「文件對齊」。

---

## 審閱修正（先於施工）

經重新交叉檢查 `backend/main.py`、`backend/routers/__init__.py`、各 router 與 `frontend/src/services/api.js`，原計畫需先修正以下事實：

1. 後端目前是 **11 個 router 模組**，不是 12 個。
2. `groups.py`、`files.py`、`jobs.py`、`processing.py`、`correction.py` 都是透過 `backend/routers/__init__.py` 掛在 `/api/projects` 之下，不是各自獨立 base path。
3. `docs/api.md` 目前提到的 `GET /projects/{project_id}/job-ids` 在後端已不存在，0.0.3 應移除，不應補寫。
4. `frontend/src/services/api.js` 仍留有少數舊方法與後端不一致，例如 `uploadPdf()`、`getProjectJobIds()`、`regenerateFromManual()`；本次文件對齊以 **後端實際 route table** 為準，並在文件中標註 legacy/deprecated 狀態。

---

## 🎯 現狀盤點 (文件 vs 程式碼 差異分析)

> [!NOTE]
> 經交叉驗證，大多數 `docs/` **已更新到 VLM-First V2**。以下逐檔標示需修程度。

| 文件 | 現有版本 | 落差程度 | 主要缺口 |
|------|---------|---------|---------|
| `api.md` | V2 | 🔴 高 | 缺 Voucher (6 條)、PDF、Groups、Files、Correction、WebSocket 路由 |
| `json_structure.md` | V2 | 🟡 中 | 缺 Voucher Layout Schema |
| `backend_architecture.md` | V2 | 🟡 中 | 缺 VoucherGenerator、VoucherLayoutRepo 模組 |
| `developer_guide.md` | V2 | 🟡 中 | 目錄樹缺 `engine/voucher_generator.py`、缺憑證開發任務指引 |
| `pipeline.md` | V2 ✅ | 🟢 低 | 已是 VLM-First，僅缺 Voucher 生成子管線 |
| `quickstart.md` | V2 ✅ | 🟢 無 | 已正確，無需修改 |
| `database.md` | V2 ✅ | 🟢 無 | 已更新為 Unified SQLAlchemy + Alembic |
| `testing_v2.md` | V2 | 🟢 低 | 可視未來需求補充 |

---

## 🛠️ 修正計畫 (版本 0.0.3)

### 更新 1: 全面補齊 `docs/api.md` (🔴 最高優先)
**目標文件**: `docs/api.md`

目前 `api.md` 只記錄了 5 個 Section (Projects, Jobs, Processing, Suggestions, Config)，但後端實際有 **11 個 router 模組**。需補齊以下缺漏：

1. **[新增] Section 6 — Voucher API** (`backend/routers/voucher.py`)
   - `GET /api/voucher/{id}/template` — 取得模板 PNG + 可用發票列表
   - `GET /api/voucher/{id}/layout` — 讀取排版草稿
   - `POST /api/voucher/{id}/layout` — 儲存排版草稿
   - `POST /api/voucher/{id}/generate` — 產出 PDF (回傳 FileResponse)
   - `GET /api/voucher/fonts/kaiu.ttf` — 取得楷體字型
   - `GET /api/voucher/{id}/image/{job_id}` — 取得發票圖片

2. **[新增] Section 7 — PDF 處理** (`backend/routers/pdf.py`)
   - 記錄 PDF 上傳、壓縮、OCR 相關路由

3. **[新增] Section 8 — 分組管理** (`backend/routers/groups.py`)
   - 記錄 `/api/projects/groups/*` 群組 CRUD 路由

4. **[新增] Section 9 — 檔案管理** (`backend/routers/files.py`)
   - 記錄 `/api/projects/{project_id}/add_files`、`raw_files`、`rotate` 路由

5. **[新增] Section 10 — 校正** (`backend/routers/correction.py`)
   - 記錄 `/api/projects/{project_id}/jobs/{job_id}/manual` 路由

6. **[新增] Section 11 — WebSocket** (`backend/routers/websocket.py`)
   - 記錄即時通知 endpoint

7. **[更新] Section 1 — Projects**
   - 標記 `POST /projects/{id}/generate-voucher-pdf` 為 **已廢棄 (Deprecated)**
   - 確認 `POST /projects/{id}/activity_info` 已記錄 ✅
   - 移除不存在的 `GET /projects/{id}/job-ids`

---

### 更新 2: 補齊 `docs/json_structure.md` Voucher Layout Schema (🟡 中)
**目標文件**: `docs/json_structure.md`

**修正內容**：
1. **新增 Section「Voucher Layout」**：定義 `layout.json` 的完整結構（與 `VoucherLayoutPayloadDraft` / `VoucherLayoutPayloadStrict` Pydantic models 對齊）
2. 包含 `globalPrefix`, `startIndex`, `pages[].fields`, `pages[].images` 的完整 Schema

---

### 更新 3: 補充 `docs/backend_architecture.md` Voucher 模組 (🟡 中)
**目標文件**: `docs/backend_architecture.md`

**修正內容**：
1. **架構圖新增 Voucher 模組**：在 mermaid 圖中加入 `VoucherGenerator` 和 `VoucherLayoutRepository`
2. **API Layer 模組清單更新**：補上 `voucher.py`, `pdf.py`, `groups.py` 等缺漏的 router
3. **Repository Layer 更新**：加入 `VoucherLayoutRepository`
4. **新增 Section 2.3**：Voucher 生成類別圖（VoucherGenerator → PyMuPDF fitz）

> [!IMPORTANT]
> 不需要「移除舊版 OCR/CV 模組」— 架構圖已經是 VLM-First 版本，只需擴充新模組。

---

### 更新 4: 擴充 `docs/pipeline.md` Voucher 子管線 (🟢 低)
**目標文件**: `docs/pipeline.md`

**修正內容**：
1. **新增 Section 5 — 憑證黏貼管線**：描述從前端 Canvas 排版 → 後端 `VoucherGenerator` → PDF 產出的完整流程

> [!NOTE]
> 不需要移除廢棄狀態 — 現有的狀態表已經是正確的 VLM-First 版本。

---

### 更新 5: 微幅擴充 `docs/developer_guide.md` (🟢 低)
**目標文件**: `docs/developer_guide.md`

**修正內容**：
1. **目錄樹更新**：在 `engine/` 下補上 `voucher_generator.py`，在 `repositories/` 下補上 `voucher_layout_repo.py`
2. **常見任務指引新增**：加一個「新增 Voucher 生成」的開發指引小節

---

## 不需修改的文件

| 文件 | 原因 |
|------|------|
| `quickstart.md` | 已正確描述 VLM-First 環境設置、micromamba、API Key 設定 |
| `database.md` | 已正確描述 Unified SQLAlchemy + Alembic 架構 |
| `testing_v2.md` | 留待未來測試覆蓋率提升時更新 |

---

## 建議實作順序

1. `docs/api.md` — 影響最大，開發者最常查
2. `docs/json_structure.md` — 前後端對接依據
3. `docs/backend_architecture.md` — 新人入門必讀
4. `docs/pipeline.md` — 補上 Voucher 子管線
5. `docs/developer_guide.md` — 微幅擴充

---

## 驗證計畫

1. **路由一致性**：逐一比對 `api.md` 中的路由與 `backend/routers/*.py` 和 `frontend/src/services/api.js` 的實際實作
2. **Schema 一致性**：確保 `json_structure.md` 與 `backend/models/voucher_payload.py` 中的 Pydantic class 100% 吻合
3. **架構圖正確性**：確保 mermaid 圖中的模組名稱與 `backend/` 目錄結構一致

> [!NOTE]
> 若發現 `frontend/src/services/api.js` 仍保留舊 route 字串，本版文件以後端為準，並只在必要處標示 legacy 差異，不把過時 client method 當成正式 API。
