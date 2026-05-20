# v0.0.22 修復與模板管理 UI 升級計畫

這個計畫旨在解決 V0.0.21 中遺留的三個主要問題：PDF 路由失效、人員管理報錯、以及模板管理缺乏圖形化介面的問題。

## 預期改動 (Proposed Changes)

### 1. 修復 PDF 任務處理 (404 Not Found)

- **原因**：後端已經寫好了 `backend/routers/pdf_tasks.py`，但在 `main.py` 裡面忘記把這個 Router 註冊進去，導致前端呼叫全部得到 404 Not Found。
- **解決方案**：
  - #### [MODIFY] [backend/main.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/main.py)
    加入 `from backend.routers.pdf_tasks import router as pdf_tasks_router` 並使用 `app.include_router(pdf_tasks_router, ...)` 註冊。

### 2. 修復人員/印章管理報錯 (500 Internal Server Error)

- **原因**：前端呼叫 `GET /api/stamps` 時，後端報錯，因為底層 SQLite 資料庫的 `stamps` 表還在用舊版的 `group_name` 欄位，而後端程式碼已經更新為查詢 `owner_id` 欄位。
- **解決方案**：
  - #### [NEW] [scripts/upgrade_db_v0_0_20.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/scripts/upgrade_db_v0_0_20.py)
    建立並執行一個資料庫升級腳本。該腳本會連線到 `workspace/global.db`，執行 `DROP TABLE stamps;` 與 `DROP TABLE groups;`，然後呼叫 `init_db()` 自動以新版 Schema (`owner_id`) 重新建立這兩張表。

### 3. 升級模板管理 UI (視覺化 Canvas 編輯器)

- **原因**：先前的模板管理直接在 `StampsManagementView.vue` 裡面放了一個 textarea 讓使用者填寫 JSON，這非常不直覺。
- **解決方案**：參考 `StampZoneConfigView.vue` 的做法，實作專屬的視覺化模板編輯頁面。
  - #### [MODIFY] [frontend/src/views/StampsManagementView.vue](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/views/StampsManagementView.vue)
    移除直接填寫 JSON 的表單。將模板列表的「新增」按鈕改為導向至新的 `/stamp-templates/create` 路由；列表中的編輯按鈕則導向至 `/stamp-templates/:id/edit`。
  - #### [NEW] [frontend/src/views/StampTemplateEditorView.vue](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/views/StampTemplateEditorView.vue)
    建立一個全新的視覺化編輯組件。這將結合 `StampZoneConfigView` 的 Canvas 預覽邏輯。
    - **主要功能**：設定模板名稱、描述。
    - **視覺化編輯**：顯示 A4 畫布，點擊與拖曳修改 6 個預設角色（經手人、社長等）的 X/Y/寬/高。
    - **保存**：將視覺化設定的座標轉換為 JSON 後發送 `PUT /api/stamp-templates/:id` 給後端。
  - #### [MODIFY] [frontend/src/router/index.js](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/router/index.js)
    新增 `/stamp-templates/create` 與 `/stamp-templates/:id/edit` 路由，指向新的編輯器組件。
