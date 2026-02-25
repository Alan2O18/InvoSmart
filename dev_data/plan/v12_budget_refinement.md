# Word Template Export Plan (v12) - Budget & Refinement

## 目標 (Goal)
基於 v11 完成的 Word 匯出主邏輯，擴建前端與後端的資料綁定，讓匯出模塊能容納所有「預算規劃」及「核備」相關的資訊。並修復資料抓取遺漏的 Bug。

## 使用者需求確認釐清 (User Requirements Clarified)
1. **補齊未綁定的佔位符 (Metadata Extension)**:
   - 原 Word 模板中含有 `{{核備日期_預算}}`、`{{核備日期_決算}}`、`{{擬請補助_原因}}`、`{{擬請補助_方式}}`、`{{結餘_處理方式}}`、`{{超支_處理方式}}`，這些都是專案層級字串 (Project Metadata)。**經確認，前端其實已經包含上述欄位 (`budgetDate`, `finalAccountDate`, `subsidyReason`, `subsidyMethod`, `balanceHandling`, `overdraftHandling`)，但後端匯出並未綁定**。
   - `{預算表(Table 0)}` 和 `{結算表(Table 1)}` 中含有 `{{預算經費列}}` 與 `{{決算經費列}}`，這屬於「經費來源 (Budget Income)」陣列。
   - `{預算表(Table 0)}` 中有 `{{預算支出列}}`，這屬於「各項費用支出預估 (Budget Expense)」陣列。
2. **前後端分離 (UI Overhaul)**:
   - 新增：將發票處理與專案報單/預算處理在 UI 上分成兩個按鈕。一個按鈕進入管理發票 (目前的 Job List)，另一個按鈕進入管理專案元資料 (Metadata) 與預算表格，並在此頁面產生 Word。
3. **Bug 修復 (Bug Fixes)**:
   - 全店促-18 遺漏問題：原因出在匯出腳本只抓取了 `vlm_result_json` (AI 初始辨識結果)，卻沒有抓 `manual_json_text` (使用者人工修改的最終資料)。
   - 0 位老師/學生：原本後端的判斷式只要數值為 0 就會返回空字串導致變為紅色佔位符。

---

## 執行計畫 (Execution Plan)

### Step 0: 核心 Bug 修復 (Critical Bug Fixes)
1. **修正資料讀取優先層級 (Word Exporter)**
   - 在 `word_exporter.py`，應優先解析 `job.get("manual_json_text")`，若無資料才 fallback 使用 `job.get("vlm_result_json")`。此修正將解決「全店促-18 (使用者自行新增修改之項目)」未被列入明細的問題。
2. **修正數值 '0' 的判定邏輯 (Word Exporter)**
   - 在 `word_exporter.py` 中計算 `t_count` 與 `s_count` 時，移除 `if t_count else ""` 的空值判斷，強制將 '0' 也視為有效數值印出，解決 `0位老師0位學生` 顯示紅字的問題。

### Step 1: 後端 Metadata 巢狀陣列擴充 (Backend Core)
1. **現有 Metadata 欄位綁定**:
   - `budgetDate`, `finalAccountDate` (字串類型)
   - `subsidyReason`, `subsidyMethod` (字串類型)
   - `balanceHandling`, `overdraftHandling` (字串類型)
2. **新增動態預算陣列欄位**:
   - `budgetIncome`: List of Object `{name: "", amount: 0, note: ""}`
   - `budgetExpense`: List of Object `{name: "", qty: 1, price: 0, total: 0, purpose: ""}`
3. **調整 `word_exporter.py` 綁定邏輯**:
   - 加入現有字串佔位符的 mapping。
   - 針對 `budgetIncome`，複製 `{{預算經費列}}` 及 `{{決算經費列}}`。
   - 針對 `budgetExpense`，複製 `{{預算支出列}}`。

### Step 2: 前端專案管理流程重構 (Frontend UI Separation)
原本 `ProjectDetailView.vue` 一頁包辦了發票管理與匯出，現在要分離為清晰的兩個流程。
1. **主控台/列表切入點 (Project List)**: 
   - 點擊專案可以選擇「發票管理」(進入原本的任務清單) 或是「預算與報表」(進入新的 metadata 編輯頁面)。
2. **新增/修改「預算與報表管理頁面」**:
   - 以 `EditProjectView.vue` 為基礎或新立 `ProjectMetaView.vue`。
   - 保留原有的基本資料 (名稱、總召、時間等)。
   - **新增「預算/核備資訊」區塊**:
     - 簡單字串輸入框 (核備日期、補助原因等)。
     - **動態陣列編輯器 (Dynamic Table Editor)** 提供使用者「新增/編輯/刪除」 `budgetIncome` 與 `budgetExpense` 項目。
   - 將「匯出 Word 報表」按鈕**移動**至此頁面，與發票管理拆分。
