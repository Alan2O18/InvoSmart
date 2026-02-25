# Word Template Export Plan (v11)

## 目標 (Goal)
將專案內的收據與明細資料，依照指定的 Word 模板 (`dev_data/空白 模板 (1).docx`) 進行匯出，並且能夠根據不同的「報帳名目 (Category)」進行跨頁分組與資料整合。

## 使用者需求確認釐清 (User Requirements Clarified)
1. **MetaData (專案層級資訊)**: 
   - 包含群組(`group`)、計畫主持人(`leader`)、計畫名稱(`projectName`)、活動日期(`startTime`/`endTime`)、地點(`location`) 等。
   - 建立專案時有輸入此資訊，後端需要確實把這包 Metadata 讀出來，才能填入 Word 模板的表頭。
2. **依品類分頁與合併 (Category Grouping & Merging)**:
   - Word 文件中，每一種不同的品類 (Category)（例如「餐食」、「茶水」）都會**獨立為一頁**。
   - **合併同品類**：如果一個專案下了多張憑證，且這些憑證都有「餐食」的明細，我們必須把它們跨憑證地**全部合併**到「餐食」的同一頁清單內。
   - **空品類處理**：若 `category` 未填寫或為空，將統一歸類至「未分類」頁面。
   - 若單一品類的資料超過一頁長度，將依賴 Word 原生的跨頁表格延伸處理自動換頁。
3. **內部憑證編號定位 (Internal Assigned ID)**:
   - 這裡指的**不是**發票/收據上原本印製的官方字軌號碼 (Invoice ID)。
   - **而是由人員/使用者自行編排並輸入的「自訂編號 / 流水號」**。
   - **實作細節**: 必須在 Job (發票層級) 的 `header` 中新增一個獨立欄位 `voucher_id`。
   - **UI 呈現**: 在 `JsonFieldEditor.vue` 的檔頭區域，增加一個明確標籤為「內部憑證編號」的輸入框。此編號將被填寫至 Word 表格的第 6 欄。

---

## 執行計畫 (Execution Plan)
此為確認階段之規劃，不涉及任何程式改動。

### Step 0: 開工前 Bug 修正與基礎設施 (Pre-work Fixes & Master Data)
#### 0.1 修正後端遺漏的 API 方法 (Pre-work Fixes)
1. **補齊資料庫方法**: 在 `ProjectRepository` (`backend/repositories/project_repository.py`) 中，實作被 `groups.py` 呼叫但遺漏的方法：
   - `list_groups(self)`
   - `upsert_group(self, group_name, leader_name)`
   - `delete_group(self, group_name)`
   - ⚠️ **重要限制**: 資料庫 `groups` 表格**僅有** `group_name TEXT` 與 `leader_name TEXT` 兩欄，無時間戳。SQL `INSERT` 必須只能寫入這兩欄，不可包含 `created_at` 等欄位。
2. **修復 Metadata 更新 Bug**: 修正 `backend/routers/projects.py` 第 84 行，將錯誤的方法名稱 `update_metadata` 改回正確的 `update_project_metadata`。

#### 0.2 前端編輯功能與中介欄位補齊 (Frontend UI & Schema Update)
1. **群組資料庫管理介面**:
   - (註：前端 `api.js` 已備妥相關 endpoint)。 在 `SettingsView.vue` 增加「👥 群組人員管理」區塊，串接上述 API。
2. **專案編輯入口補齊**: `EditProjectView.vue` (路由已確認為 `/edit/:id`) 需要在 `ProjectDetailView.vue` 中增加按鈕供使用者點擊進入。
3. **新增獨立憑證編號欄位 (Dedicated Voucher ID)**:
   - 在 `CreateProjectView.vue` 與 `EditProjectView.vue` 實作：
     - 當使用者選取「組別」時，系統自動從資料庫查詢對應的「組長」並自動填入 input。
3. **前端/Schema 欄位擴充**:
   - 在 `EditProjectView.vue` 與 `CreateProjectView.vue` 中新增**「活動總務 (General Affairs)」**欄位，與原有的「活動總召 (Coordinator)」區分開來。
   - 在 `JsonFieldEditor.vue` 加入 `voucher_id` 欄位供獨立編排憑證編號。
4. **入口補齊**: 在 `ProjectDetailView.vue` 增加「編輯活動資訊」按鈕，導向 `EditProjectView.vue`。

### Step 1: 解析與資料對應 (Template Mapping)
1. **Word 佔位符對應表**:
   - `{{組別}}` -> `project.metadata.group`
   - `{{組長}}` -> `project.metadata.leader`
   - `{{活動名稱}}` -> `project.metadata.name`
   - `{{活動總召}}` -> `project.metadata.coordinator`
   - `{{活動總務}}` -> `project.metadata.generalAffairs` (取代原本硬編碼的「活動總務：李天旭」)
   - `{{活動期間}}` -> `project.metadata.startTime` ~ `endTime`
   - `{{活動地點}}` -> `project.metadata.location`
   - `{{總人數}}` -> `teacherCount + studentCount`
   - ⚠️ **未填欄位處理**: 尋訪所有的佔位符 (包括預算表 Table 0)，**如果對應的資料為空值或未填寫，則不要刪除該佔位符，而是將該文字實體標記為「紅色字體」**，以利使用者後續人工檢查補齊。
2. **Backend 補齊**: 確保匯出 API 能一次取得 Project Metadata + 全部的 Job Items。
   - 文件包含兩張主要表格：
     - **Table 0 (預算表)**: 暫不處理。
     - **Table 1 (結算表)**: 匯出核心。
       - **Metadata 佔位符**: `{{組別}}`, `{{組長}}`, `{{活動名稱}}`, `{{活動總召}}`, `{{活動期間}}`, `{{活動地點}}`, `{{總人數}}`, `{{老師人數}}`, `{{學生人數}}` 等。
       - **明細插入點**: 第 12 列 (Row 12) 含有 `{{決算支出列}}`。標題列為 `['項目名稱', '數量', '單價', '金額', '說明用途', '憑證編號']`。
   - **技術挑戰**: `python-docx` 不支援直接跨文件或跨頁複製表格。我們將使用 `copy.deepcopy` 操作 `_element` (XML) 來達成 Table 結構（含合併儲存格）的完美複製。
   - **變數置換**: 針對 Word 中文字可能被拆分為多個 `Run` 的情況，將實作 `replace_text_in_paragraph` 函式，先合併文字再進行取代，確保佔位符能被正確識別。

### Step 2: 實作核心匯出邏輯 (`word_exporter.py`)
1. **發票資料扁平化與分類 (Data Aggregation)**:
   - 讀取該專案下所有的 Job。
   - 攤平每張 Job 的 `items` 陣列。
   - 為每個 Item 綁定它所屬 Job 的 **「自訂內部編號 (Assigned ID)」** 與日期。
   - 以 `category` 作為 Key 進行分類 (Group-By)，把相同品類的明細全部聚合。

2. **Word 報告生成 (Docx Generation)**:
   - 開啟 `.docx` 模板。
   - **外層迴圈**：歷遍每個 `category`（餐食、茶水...）。
     - 【如果是第二個品類以上】：插入分頁符 (Page Break)，複製整個文件結構或 Table 1 結算表。
     - **寫入 Metadata**：尋找 Table 中如 `{{活動名稱}}` 的儲存格並執行字串替換。可以在活動名稱加上副標題如 `{{活動名稱}} - {category}`。
     - **內層迴圈**：定位含有 `{{決算支出列}}` 的那一個 Row。
       - 對於該品類下的每一個明細，向上方 (或下方) 新增一列。
       - 填入: **項目名稱(`name`)**、**數量(`qty`)**、**單價(`price`)**、**金額(`total`)**、**說明用途("")**、**憑證編號(自訂內部編號)**。
       - 清除或隱藏原本印有 `{{決算支出列}}` 的那一列。
     - **計算總和**：加總此品類的金額，寫入表格 `{{決算_支出總計}}` 佔位符。
   - **實體檔案輸出**: 將組合完成的檔案儲存至使用者的**本地專案目錄**內。
     - **路徑定義**: `engine.project_repo._project_root(project_id) / "Word匯出"`
     - **實際位置範例**: `c:\Users\tange\Desktop\all_project\py for NKNU GA\AI_AGENT_LAB\projects\{Project_ID}\Word匯出\{Project_ID}_word_export.docx`

3. **前端/API串接**:
   - 提供 `POST /api/projects/{project_id}/run_word_export`。
   - API 回傳新產生的檔案路徑，供前端提供下載連結給使用者。

### Step 3: 擴充專案 Metadata 與前端預算建置 (Budget & Approval Data)
因為原模板含有額外的「預算」與「核備」佔位符。
1. **新增字串與日期欄位 (Project Metadata)**:
   - `approvalDateBudget` -> `{{核備日期_預算}}`
   - `approvalDateFinal` -> `{{核備日期_決算}}`
   - `subsidyReason` -> `{{擬請補助_原因}}`
   - `subsidyMethod` -> `{{擬請補助_方式}}`
   - `surplusMethod` -> `{{結餘_處理方式}}`
   - `deficitMethod` -> `{{超支_處理方式}}`
2. **新增動態陣列 (Budget Arrays in Metadata)**:
   - `budgetIncome`: `[{name, amount, note}]` -> 取代 `{{預算經費列}}` 與 `{{決算經費列}}`
   - `budgetExpense`: `[{name, qty, price, total, purpose}]` -> 取代 `{{預算支出列}}`
3. **前端 UI 實作**:
   - 在 `EditProjectView.vue` 底部擴充一塊「預算與核備資訊」區塊。
   - 提供可以動態新增/刪除列的 UI 介面來填寫經費來源與預估支出。
4. **後端 Word Exporter 實作**:
   - 於 `_replace_text_in_table` 前，利用 `_copy_table_after` 與 `_find_row_with_placeholder` 將 `budgetIncome` 加到 Table 0 與 Table 1 中。
   - 處理 `budgetExpense` 寫入 Table 0 的 `{{預算支出列}}`。
