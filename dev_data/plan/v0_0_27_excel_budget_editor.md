# v0.0.27 計畫：Excel 預算/決算編輯器與樹狀全覽大表

本計畫旨在優化現有的專案預算與決算管理流程，將原本分散、零碎的輸入框替換為高效流暢的 **Excel-like 試算表編輯器**，並建立一個支援樹狀摺疊/展開的**全專案預決算總覽大表**，提升財務申報的處理效率。

---

## 1. 功能需求與介面設計

### A. 獨立 Excel 預算編輯工作區 (`BudgetEditorView.vue`)
* **路徑**：`/project/:id/budget-editor`
* **介面結構**：全螢幕無干擾工作區，頂部包含「返回專案」、「儲存修改」與「匯出 Word」常駐按鈕。下方使用 Tab 分割為兩個獨立編輯表：
  1. **預算表 (Budget)**
     * **經費來源 (收入)**：來源名稱、預算金額、備註。直接儲存至 `project.metadata.budgetIncome`。
     * **費用支出 (支出)**：項目名稱（科目別）、數量、單價、總額（自動計算）、用途說明。直接儲存至 `project.metadata.budgetExpense`。
  2. **決算表 (Final Account)**
     * **實際經費來源 (收入)**：唯讀或直接帶入預算經費來源。
     * **實際費用支出 (支出)**：
       * **平行載入**：因後端無單一端點返回所有 Jobs 的品項明細，前端需先調用 `api.getProjectJobs(projectId)` 取得 Job 列表，篩選 `status === 'done'` 的 Jobs，再利用 `Promise.all` 並行調用 `api.getJobDetails(projectId, jobId)` 獲取完整 JSON 並扁平化展開為網格。
       * **變更追蹤 (Change Tracking)**：使用以 `{jobId, itemIndex}` 為鍵的 2D 變更對照表（Change Map）。當使用者編輯網格時，僅更新本機對應 Job 的明細，並將該 Job 標記為已修改。
       * **微粒化儲存**：儲存時，前端只對有修改的 Job 呼叫 `api.saveManualJson(projectId, jobId, jobDetails.vlm_result)`，保留其他未修改發票的完整原始品項。
* **網格核心互動**：
  * **鍵盤導航**：支援 `↑` `↓` `←` `→` 箭頭鍵與 `Tab` / `Enter` 切換儲存格焦點。
  * **Excel 複製貼上**：攔截貼上事件，解析 TSV（Tab Separated Values）字串以支援與 Google Sheets / Excel 的雙向複製貼上。
  * **合計欄位與空狀態**：表尾即時動態加總。若資料為空，顯示「+ 新增第一筆」按鈕以引導使用者快速建立新資料列。

### B. 樹狀總覽看板 (`ProjectsOverviewView.vue`)
* **路徑**：`/projects/overview`
* **介面結構與效能優化**：
  * **懶載入策略 (Lazy Loading)**：後端沒有全域聚合端點。首頁總表預設僅載入專案基本資訊與預算總計。當使用者點擊展開某專案時，才動態載入該專案的 Job 詳情（使用上述的 Promise.all 載入），並計算其實際支出與差額。這可避免一次載入所有專案的發票明細導致瀏覽器卡頓或後端負載過高。
  * **首頁總表**：列出所有專案的 Project ID、名稱、預算總計、決算總計（已展開專案顯示實際值，未展開專案可點擊以載入/計算）與差額。
  * **摺疊與展開**：每一行專案均可點擊向下展開 tree 面板，內嵌展示該專案詳細的預算表與決算表清單，無需切換頁面即可進行快速對帳。


---

## 2. 檔案異動清單

### 路由與選單
* **[MODIFY]** `frontend/src/router/index.js`
  * 註冊 `/project/:id/budget-editor` (BudgetEditorView)
  * 註冊 `/projects/overview` (ProjectsOverviewView)
* **[MODIFY]** `frontend/src/App.vue`
  * 導航列加入「預決算總覽 (Overview)」連結。

### 專案詳細頁面
* **[MODIFY]** `frontend/src/views/ProjectDetailView.vue`
  * 將「編輯預算與報表」按鈕重導向至新建立的 `/project/:id/budget-editor`。

### 新增編輯與全覽視圖
* **[NEW]** `frontend/src/views/BudgetEditorView.vue`
  * 實現自訂的 Excel-like 鍵盤導航網格、TSV 複製貼上模組與發票分組保存邏輯。
* **[NEW]** `frontend/src/views/ProjectsOverviewView.vue`
  * 實現全專案的樹狀摺疊表格與收支統計看板。

---

## 3. 實作步驟

### 第一階段：路由與入口調整
1. 在 `router/index.js` 註冊新路由。
2. 調整 `ProjectDetailView.vue` 上的按鈕連結。
3. 在 `App.vue` 加入導航選單。

### 第二階段：Excel 網格核心元件與預算編輯器
1. 實作 Excel-like 表格編輯器，包括箭頭鍵切換與 `Tab`/`Enter` 移動 Focus。
2. 實作 TSV 格式的 Clipboard 讀取與貼上解析。
3. 實作 預算頁籤（收入與支出）並進行數據存取整合。

### 第三階段：決算表發票資料綁定與分組保存
1. 載入 `done` 狀態發票數據並扁平化。
2. 在決算表格中展現明細，並將修改內容與 Job / Item Index 進行映射綁定。
3. 實作分組回存功能，依次提交變更至各個發票。

### 第四階段：總覽大表與樹狀摺疊
1. 實作 `ProjectsOverviewView.vue` 大表。
2. 實作樹狀摺疊面板，動態加總呈現每個專案的收支數據。

---

## v0.0.27 變更紀錄 (Changelog Updates)
* **新增預設值設定**：專案設定（ProjectSettingsModal.vue）中「擬請補助原因」、「擬請補助方式」、「結餘處理方式」與「超支處理方式」四個財務欄位在為空時，系統將預設自動填入【無】。
* **TSV 雙向匯出/匯入**：經費編輯器與大表的各個資料表格新增獨立的「📤 匯出 TSV」與「📥 匯入 TSV」按鈕，實作彈出式 TSV 文字載入面板，支援與試算表軟體（Excel/Google Sheets）的快捷導入與導出。
* **下拉式建議選單**：對接後端建議詞庫 APIs，為經費項目的名稱、科目與類別輸入框提供動態的 datalist 下拉式建議選項。
* **預決算全覽大表內嵌編輯模式**：大表（ProjectsOverviewView.vue）展開面板新增「編輯模式」切換開關，開啟時表格直接轉化為輸入格，支援 inline 新增、刪除、TSV 匯出/匯入，並能一鍵儲存回後端，無需離開總覽頁。

---

## 4. 追加實作步驟（新增 2 段工程）

### 第五階段：專案設定預設值與 TSV 匯出/匯入及建議選項（工程 1）
1. 修改 `ProjectSettingsModal.vue`，確保「擬請補助原因」、「擬請補助方式」、「結餘處理方式」與「超支處理方式」在無值時預設填入【無】。
2. 在 `BudgetEditorView.vue` 中載入建議詞庫，並將建議詞庫的 `<datalist>` 綁定至預算收入項目、預算支出項目以及決算支出科目。
3. 在 `BudgetEditorView.vue` 中為各個經費表格（預算收入、預算支出、決算支出各 Job 區塊）新增獨立的「匯入 TSV」與「匯出 TSV」按鈕，並實作彈出式 TSV 文字匯入/匯出 Modal，支援直接貼上 Excel 複製的資料進行資料列覆蓋或附加。

### 第六階段：預決算全覽大表支援內嵌編輯模式（工程 2）
1. 修改 `ProjectsOverviewView.vue`，在展開面板中新增「編輯模式」切換。
2. 當開啟編輯模式時，將預算支出表格與決算支出表格轉化為可編輯的輸入框，並為其綁定建議詞庫的 Datalist。
3. 實作預算支出的「新增項目」、「刪除項目」與「儲存預算」，決算支出各 Job 區塊的「新增品項」、「刪除品項」與「儲存決算」功能。
4. 在全覽大表各區塊新增「匯入 TSV」與「匯出 TSV」按鈕，實作彈出式 TSV 文字匯入/匯出互動 Modal，實現無縫的預決算全覽編輯回存。
