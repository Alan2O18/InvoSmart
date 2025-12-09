# 前端 Frontend

本專案使用 Vue 3 + Vite 建置，提供直覺的使用者介面來管理發票處理活動。

> **最後更新**：2025-12-09（活動術語重構與 UI 改進完成後）

## 技術堆疊

- **框架**：Vue.js 3 (Composition API + `<script setup>`)
- **建置工具**：Vite
- **路由**：Vue Router
- **HTTP 客戶端**：Axios
- **樣式**：CSS（深色主題設計）

## 專案結構

```
frontend/
├── src/
│   ├── views/              # 頁面元件
│   │   ├── HomeView.vue              # 活動列表頁
│   │   ├── CreateProjectView.vue    # 建立活動頁
│   │   ├── EditProjectView.vue      # 編輯活動頁
│   │   ├── ProjectDetailView.vue    # 活動詳情頁
│   │   └── EditJobView.vue          # 編輯工作頁
│   ├── services/           # API 服務層
│   │   └── api.js          # API 整合
│   ├── App.vue             # 根元件
│   └── main.js             # 應用程式進入點
├── public/                 # 靜態資源
├── index.html              # HTML 模板
└── vite.config.js          # Vite 設定
```

## 主要功能

### 1. 活動管理
- **列表檢視** (`HomeView.vue`)
  - 顯示所有活動（使用「活動」術語）
  - 即時狀態顯示（自動從後端同步）
  - 快速操作：編輯、刪除活動
  
- **建立活動** (`CreateProjectView.vue`)
  - 活動 ID 與活動名稱（必填）
  - 群組、負責人、時間等 metadata
  - 批次上傳發票圖片
  
- **編輯活動** (`EditProjectView.vue`)
  - 修改活動名稱與 metadata
  - 活動 ID 唯讀顯示
  - 編輯後不會重置活動狀態

### 2. 處理管線
- **活動詳情** (`ProjectDetailView.vue`)
  - 五階段處理流程：Split → OCR → LLM → Export → Archive
  - 原始檔案管理（上傳、分割、刪除）
  - 工作列表與狀態監控
  - 即時狀態更新（每 2 秒輪詢）

### 3. 工作監控
- **狀態顯示改進**
  - 點擊「Run OCR (All)」或「Run LLM (All)」後立即顯示 Pending 狀態
  - Run/Rerun 按鈕在處理中時自動隱藏
  - 清楚的狀態徽章（Ready, Pending, Running, Done）

- **個別工作操作**
  - 執行單一 OCR/LLM
  - 圖片旋轉（90° 或 -90°）
  - 工作刪除

### 4. 人工修正
- **編輯工作** (`EditJobView.vue`)
  - 查看 OCR 結果
  - 修正 LLM 提取的資料
  - 儲存修正並重新生成

## 開發指南

### 安裝相依套件

```bash
npm install
```

### 開發模式

```bash
npm run dev
```

前端將運行於 `http://localhost:5173`

### 建置生產版本

```bash
npm run build
```

建置結果將輸出至 `dist/` 目錄。

### 預覽生產版本

```bash
npm run preview
```

## API 整合

所有 API 呼叫透過 `src/services/api.js` 統一管理：

```javascript
import api from '@/services/api'

// 範例：取得所有活動
const response = await api.getProjects()
const activities = response.data
```

### 主要 API 方法

- `getProjects()` - 取得活動列表
- `createProject(formData)` - 建立新活動
- `updateProject(id, metadata)` - 更新活動
- `deleteProject(id)` - 刪除活動
- `getProject(id)` - 取得活動狀態
- `getProjectJobs(id)` - 取得工作列表
- `runOCR(id)` - 執行批次 OCR
- `runLLM(id)` - 執行批次 LLM

## 最近更新

### 2025-12-09 活動術語重構

**UI 更新**：
- 所有頁面從「專案」改為「活動」
- 表格欄位：活動名稱、活動 ID
- 按鈕文字：「+ New Activity」、「Create Activity」

**資料映射**：
- 前端「活動名稱」→ 後端 `name` 欄位
- 前端「活動 ID」→ 後端 `project_id`（主鍵）
- 其他欄位 → 後端 `metadata` JSON

**狀態一致性**：
- HomeView 和 ProjectDetailView 都使用資料庫狀態
- 後端自動同步狀態（基於檔案和 jobs 進度）
- 編輯活動不會重置狀態

### 2025-12-09 工作狀態顯示改進

**即時反饋**：
- 批次操作後 100ms 內更新狀態
- pending/running 狀態即時顯示

**按鈕邏輯**：
- 新增 `canShowOCRButton()` 和 `canShowLLMButton()` 函數
- 處理中時隱藏 Run/Rerun 按鈕
- 完成後才顯示 Rerun 按鈕

## 樣式設計

### 深色主題
- 主背景：`#1a1a1a`
- 卡片背景：`#2a2a2a`
- 邊框：`#444`
- 文字：`#e0e0e0`

### 狀態徽章顏色
- NEW: 藍色 `#3b82f6`
- SPLIT: 紫色 `#8b5cf6`
- PROCESSING: 橙色 `#f59e0b`
- PROCESSED: 綠色 `#10b981`
- ARCHIVED: 靛青色 `#6366f1`
- SEALED: 灰色 `#64748b`

## IDE 支援

推薦使用 [VSCode](https://code.visualstudio.com/) 配合以下擴充套件：

- [Vue - Official](https://marketplace.visualstudio.com/items?itemName=Vue.volar)（之前稱為 Volar）
- [ESLint](https://marketplace.visualstudio.com/items?itemName=dbaeumer.vscode-eslint)

詳細資訊請參考 [Vue 官方文檔 - IDE 支援](https://vuejs.org/guide/scaling-up/tooling.html#ide-support)
