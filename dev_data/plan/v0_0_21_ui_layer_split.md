# v0.0.21 使用者體驗與路由架構重構計畫

## 核心動機
目前的頁面架構與路由設計過於扁平，且把不同產品線混在同一組頁面裡，導致使用者容易混淆。v0.0.21 的目標是把系統拆成三條清楚的線：發票/憑證貼章線、獨立 PDF 任務線、以及人員/組別/印章管理線。

## 先釐清既有職責
- `SettingsView` 只保留系統設定，不再承載群組人員管理或電子章上傳。
- `StampsManagementView.vue` 是新的管理中心基底，`/management` 路由應導向這個頁面並重構成正式的管理介面。
- `VoucherEditorView.vue` 仍然是發票/憑證貼章編輯器，只負責憑證編輯與 PDF 產出，不屬於新的 `/pdf-tasks` 線。
- 舊的群組人員管理與電子章上傳 UI 視為舊功能，應從 `SettingsView` 移除，不要再沿用原介面。

## 預期改動與目標

### 1. 新增頂級入口首頁 (Landing Page)
- 將系統 `/` 路由指派給一個全新的首頁組件（如 `LandingView.vue`）。
- 畫面上提供四個視覺強烈、清晰的大型入口按鈕：
  1. 🧾 **發票憑證處理系統**：導向傳統的專案/切圖流程。
  2. 📄 **獨立 PDF 任務處理**：導向全新的 PDF 專用工作流。
  3. ⚙️ **設定**：進入系統設定頁面（現有 `SettingsView`）。
  4. 👥 **管理**：進入統一管理頁面，包含人員、印章、蓋章區域、憑證模板等。

### 2. 現有首頁降級 (HomeView -> ProjectsView)
- 把現有顯示「所有專案列表」的 `HomeView.vue` 移動至二級路由（例如：`/projects` 或 `/vouchers`）。
- 這條業務線繼續負責原本的：上傳圖片 -> 裁切 -> 生成發票流水號 -> 歸檔等功能。

### 3. 新建 PDF 任務主頁 (PDF Main Dashboard)
- 建立 `/pdf-tasks` 路由，這是一條新的 PDF 任務線，和 `VoucherEditorView.vue` 完全分開。
- **第一層（任務列表）**：顯示所有已上傳的 PDF 檔案清單。
  - 每個 PDF 顯示狀態（已上傳、處理中、已完成、錯誤等）。
  - 可篩選、搜尋、排序 PDF 列表。
  - 上傳新 PDF 的入口也放在這一層。
- **第二層（編輯工作區）**：點進某個 PDF 後進入編輯頁面 (`/pdf-tasks/:pdf-id/editor`)。
  - 頁面頂部選擇「蓋章模板」（對應不同的版式/憑證類型）。
  - 功能按鈕：
    - **單頁蓋章**：對當前頁選擇並應用某個角色的章。
    - **全頁蓋章**：對整份 PDF 全頁應用某個角色的章。
    - **壓縮**：壓縮 PDF 檔案大小。
    - **編輯頁序**：刪除特定頁面 / 新增頁面 / 調整順序。
  - 先看到文件狀態，再點進去進入編輯區。
  - 即時預覽編輯結果。

### 4. 導航列與麵包屑更新 (Navigation UX)
- 頂部導航列 (Navbar) 的 Logo 預設回退至頂級入口首頁。
- 增加全域導航選單或側邊欄，讓使用者能清楚知道自己目前身處「發票線」、「PDF 線」還是「管理線」，並可隨時切換。

### 5. 人員 / 組別 / 印章管理頁面 (ManagementView)
- 新建一個 `/management` 路由，實際頁面以現有 `StampsManagementView.vue` 為基礎重構。
- 這裡是新的管理中心，不再沿用 `SettingsView` 裡的群組人員管理與電子章上傳區塊。
- 子模組或分頁應包含：
  - **人員管理**：建立、刪除、編輯人員，指定角色。
  - **組別管理**：建立、刪除、編輯組別與關聯。
  - **印章管理**：檢視、上傳、刪除印章，並按擁有者/角色分類。
  - **蓋章區域配置**：定義各個角色在憑證上的蓋章位置。
  - **上傳/管理蓋章模板**：支援多種版型，每個模板可獨立配置各角色座標，並提供新增、編輯、刪除、啟用/停用功能。
  - **憑證模板設定**：編輯發票/憑證的版型、欄位配置。
- 舊的群組人員管理與電子章上傳流程不保留原 UI；若保留印章匯入能力，也要以新的管理介面重新設計。

## 執行步驟 (Execution Steps)

- **Phase 1: 建立頂級入口與調整路由**
  建置 `LandingView.vue`，同時修改 `router/index.js`，把原 `HomeView` 降級到二級頁面。
- **Phase 2: PDF 任務主頁 Scaffold**
  建置 `/pdf-tasks` 的任務列表與 PDF 編輯工作區，明確與 `VoucherEditorView.vue` 分開。
- **Phase 3: 管理中心重構**
  以 `StampsManagementView.vue` 為基底重構 `/management`，整合人員、組別、印章、模板與蓋章區域管理。
- **Phase 4: 導航結構重寫**
  更新 `App.vue` 或 Layout 組件，實作新層級的 Navbar 與麵包屑，支援快速返回頂級首頁。
- **Phase 5: 確認舊有流程未受損**
  測試發票/憑證線進入專案後的流程仍可產出 PDF，且不會誤連到新的 `/pdf-tasks` 線。

## 新路由結構 (Routing Map)

```
/ (Landing Page - 一級入口)
├── /projects (Projects List - 發票憑證處理系統)
│   ├── /create (Create Project)
│   ├── /project/:id (Project Detail)
│   ├── /project/:id/edit-job (Job Editor)
│   ├── /project/:id/stamp-preview (Voucher Stamp Preview)
│   ├── /project/:id/voucher-editor (Voucher Editor)
│   ├── /edit/:id (Edit Project)
│   └── /voucher-template-config (Voucher Template Config)
├── /pdf-tasks (PDF Dashboard - PDF 任務列表)
│   └── /pdf-tasks/:pdf-id/editor (PDF Editor - 編輯工作區)
├── /management (Unified Management Panel - 人員/組別/印章管理)
├── /settings (System Settings - 設定)
└── (Legacy - 轉址或廢棄)
    ├── /stamps -> /management
    └── /stamp-zones -> /management
```

## 功能細節說明 (Detailed Feature Specs)

### 蓋章模板管理 (Stamp Zone Templates)
- **核心概念**：不同憑證版式需要不同的蓋章位置。
- **操作流程**：
  1. 在「管理」頁面中建立新模板（例如：「2026年發票版」）。
  2. 上傳或選擇參考圖片，標記各角色的蓋章區域座標。
  3. 系統保存此模板配置。
  4. 在「發票/憑證編輯」或「PDF 編輯」時可選用此模板。
- **模板屬性**：
  - 名稱、描述、版型代碼
  - 各角色的蓋章座標集合（可根據解析度自動縮放）
  - 啟用/停用狀態

### PDF 編輯工作區流程 (PDF Editor Workflow)
1. 使用者在「PDF 任務列表」(`/pdf-tasks`) 中上傳 PDF。
2. 每個 PDF 顯示「待處理」狀態。
3. 點擊 PDF 進入「編輯工作區」(`/pdf-tasks/:pdf-id/editor`)。
4. **編輯工作區功能**：
   - **頂部控制欄**：選擇蓋章模板下拉選單。
   - **左側面板**：PDF 頁面預覽縮圖。
   - **中央編輯區**：當前頁面的大圖預覽。
   - **右側工具欄**：
     - 📌 **單頁蓋章**：當前頁指定角色蓋印。
     - 📌 **全頁蓋章**：整份 PDF 全頁蓋相同角色的印。
     - 📦 **壓縮**：壓縮 PDF 檔案。
     - ❌ **刪除頁面**：移除不需要的頁面。
     - ➕ **新增頁面**：插入其他 PDF 或圖片頁面。
     - 🔄 **調整頁序**：拖曳重新排列頁面順序。
   - **儲存/下載**：完成編輯後下載已蓋章的 PDF。
5. 狀態更新為「已完成」。

### 設定頁面改動 (SettingsView Updates)
- **移除的功能**：
  - ❌ 人員管理
  - ❌ 組別管理
  - ❌ 電子章上傳
- **保留的功能**：
  - 系統全域參數設定
  - 模型設定
  - 其他工具選項
- **備註**：這些功能全部搬到 `/management`，`SettingsView` 只保留純設定項目。

## 後端配合需求 (Backend Integration Requirements)

### 蓋章模板 API
- `POST /api/stamp-templates` - 建立新蓋章模板
- `GET /api/stamp-templates` - 列出所有蓋章模板
- `GET /api/stamp-templates/:id` - 取得單個蓋章模板詳細資訊
- `PUT /api/stamp-templates/:id` - 更新蓋章模板
- `DELETE /api/stamp-templates/:id` - 刪除蓋章模板

### PDF 處理 API
- `POST /api/pdf-tasks` - 上傳新 PDF
- `GET /api/pdf-tasks` - 列出所有 PDF 任務
- `GET /api/pdf-tasks/:id` - 取得單個 PDF 任務詳細資訊
- `PUT /api/pdf-tasks/:id` - 更新 PDF 任務（蓋章、壓縮、編輯頁序等）
- `DELETE /api/pdf-tasks/:id` - 刪除 PDF 任務
- `POST /api/pdf-tasks/:id/apply-stamp` - 在 PDF 上應用蓋章
- `POST /api/pdf-tasks/:id/compress` - 壓縮 PDF
- `POST /api/pdf-tasks/:id/page-operations` - 頁面操作（刪除、新增、重排）

### 既有憑證 API
- 現有 `voucher/*` 與 `project/*` API 繼續服務 `VoucherEditorView.vue` 與原本的發票/憑證線。
- 這一條線只負責憑證貼章與 PDF 產出，不併入新的 `/pdf-tasks` 流程。
