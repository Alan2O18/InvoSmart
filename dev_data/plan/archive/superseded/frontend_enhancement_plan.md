# 前端體驗優化計畫：智慧編輯與圖片檢視 (Final Frontend Enhancement Plan v3)

本計畫旨在解決用戶在實際操作中遇到的痛點，提供高效的人工修正與檢視工具。

## 1. 核心目標
1.  **加速人工修正流程**：提供強大的 JSON 編輯器與快速欄位修正，減少編輯時間。
2.  **提升檢視體驗**：實作類似 Google Maps 的圖片檢視器，支援細節查看。
3.  **操作便捷性**：全鍵盤操作支援與批次處理。

## 2. 功能詳細規格與技術解法

### 2.1 📷 進階圖片檢視器 (Advanced Image Viewer)
實作一個互動式檢視器，取代原本靜態的 `<img>` 標籤。

*   **功能需求**：
    *   **滾輪縮放 (Zoom)**：
        *   範圍：`0.1x` ~ `5.0x`。
        *   行為：以滑鼠游標為中心進行縮放 (Zoom to Cursor)。
        *   **指示器**：角落顯示當前縮放倍率 (e.g., `150%`)。
        *   **渲染優化**：加入 CSS `image-rendering: auto` (預設) 與 `pixelated` (高倍率) 切換，確保文字清晰。
    *   **拖曳移動 (Pan)**：
        *   行為：放大狀態下，按住左鍵拖曳。
        *   **邊界限制**：防止圖片完全拖出視窗，至少保留 `20%` 可見區域。
        *   **阻尼效果**：加入 `transition: transform 0.1s ease-out` 讓移動更滑順。
    *   **適應視窗 (Fit)**：
        *   行為：雙擊圖片或點擊「Reset」，自動調整至 `fit-contain` 模式。
        *   **初始比例**：`scale = fitScale` (而非固定 `1x`)，確保圖片完整顯示。

*   **技術挑戰與解法**：
    *   **縮放基準點 (Transform Origin)**：
        *   **解法**：動態計算 `translate` 補償。
    *   **Resize Observer**：
        *   **解法**：監聽容器大小變化，自動校正圖片位置。

### 2.2 ⚡ 智慧 JSON 編輯器 (Smart JSON Editor)
引入專業程式碼編輯體驗，並加入「快速欄位」解決 JSON 結構複雜的問題。

*   **技術選型**：
    *   **核心庫**：`vue-codemirror@^6.1.1` (Vue 3 專用, CodeMirror 6)。
    *   **依賴**：`codemirror`, `@codemirror/lang-json`, `@codemirror/lint`, `lodash-es` (Tree Shaking)。

*   **功能需求**：
    *   **語法高亮 & Linting**：清晰區分 Key/Value，即時偵測語法錯誤。
    *   **快速欄位 (Quick Fields Sync)**：
        *   提供 `Date`, `Invoice ID`, `Total` 獨立輸入框。
        *   **路徑映射 (Field Mapping)**：定義可配置的路徑表，支援不同 VLM 輸出格式。
        *   **空路徑處理**：若 JSON 中無對應路徑，Quick Field 顯示空白；首次輸入時自動建立路徑。
    
*   **技術挑戰與解法**：
    *   **無限循環更新 & 游標丟失**：
        *   **解法**：
            1.  **鎖定機制**：僅當 Quick Field 值 != JSON 解析值時觸發。
            2.  **Dispatch Changes**：更新 JSON 字串時使用 `editor.dispatch({ changes: ... })` 而非重設 `v-model`，保留游標位置。
    *   **Prettify 與 isDirty 衝突**：
        *   **解法**：`isDirty` 判定應比較 `JSON.stringify(JSON.parse(str))` (語意相等) 而非純字串比較。
    *   **快捷鍵攔截**：
        *   **解法**：將自訂快捷鍵 (Ctrl+S) 註冊在 CodeMirror 的 `keymap.of()` 最高優先級。

### 2.3 ⌨️ 導航與快捷鍵 (Navigation & Shortcuts)
*   **Job 導航**：
    *   **需求**：在編輯檢視中直接切換到「上一張」或「下一張」Job。
    *   **效能優化**：
        *   **輕量 API**：建立 `GET /api/projects/{id}/job-ids` 僅回傳 ID 列表。
        *   **圖片預載 (Preload)**：切換前預先載入下一張圖片 (`new Image().src = ...`)。
*   **狀態重置 (State Reset)**：
    *   **解法**：切換 Job 時手動重置：
        *   ImageViewer: `scale = fitScale`, `translate = 0,0`。
        *   Editor: 清空 Undo History。

## 3. 實作步驟 (Implementation Steps)

### Phase 1: 圖片檢視器 (P0 - High Priority)
1.  **PoC**: 建立 `tests/poc_image_zoom.html` 驗證 Zoom-to-Cursor 與 Fit Scale 邏輯。
2.  **Create Component**: `src/components/ImageViewer.vue`
    *   Props: `src`, `alt`.
    *   State: `scale`, `translateX`, `translateY`.
    *   UI: Scale Indicator, Reset Button.
3.  **Integrate**:修改 `src/views/JobEditorView.vue`
    *   替換 `<img ...>` 為 `<ImageViewer ... />`。

### Phase 2: JSON 編輯器升級 (P1)
1.  **PoC**: 建立 Vue Demo 驗證 `vue-codemirror` 雙向綁定與游標保留。
2.  **Install**: `npm install vue-codemirror@^6.1.1 ...`.
3.  **Create Component**: `src/components/SmartJsonEditor.vue`
    *   封裝 CodeMirror。
    *   實作 Field Mapping, Sync Logic, Prettify。
4.  **Integrate**: 修改 `JobEditorView.vue`。

### Phase 3: 導航架構 (P2)
1.  **Backend API**: 新增 `GET /api/projects/{id}/job-ids`。
2.  **Frontend Logic**:
    *   實作 `goToPrev` / `goToNext` (含 Preload)。
    *   加入 `isDirty` 檢查 (語意比較)。
    *   實作 `Ctrl+S` 攔截。

## 4. 驗證計畫 (Verification Plan)
*   **圖片檢視**：
    *   測試長條圖是否以 `fitScale` 初始顯示。
    *   測試快速縮放時，文字邊緣是否清晰 (`image-rendering`)。
*   **JSON 編輯**：
    *   測試自動排版後，`isDirty` 是否保持為 false。
    *   測試在 Quick Field 輸入時，JSON Editor 游標是否保留。
*   **導航**：
    *   按 `Ctrl+S` 確認觸發 API 儲存。
    *   快速切換 Job，確認圖片無閃爍 (Preload 生效)。
