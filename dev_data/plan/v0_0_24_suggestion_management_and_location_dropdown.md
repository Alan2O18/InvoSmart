# v0.0.24 推薦詞管理與地點下拉補完計畫

**狀態**: ✅ 已完成

## 核心目標
目前系統已經有推薦詞的「新增 / 查詢」能力，但還沒有真正可用的「編輯 / 刪除 / 管理」介面；同時，活動地點欄位也還是純文字輸入，沒有推薦詞下拉選單。v0.0.24 要做的是把這兩個小缺口補齊，讓推薦詞系統能真的用在日常建檔流程。

## 現況確認

1. `backend/routers/suggestions.py` 目前只有查詢、新增、批次新增，沒有完整的 CRUD。
2. `backend/repositories/suggestion_repository.py` 已有 `search / add_or_update / bulk_add`，但沒有 `list / get / update / delete` 之類的管理方法。
3. `backend/repositories/suggestion_repository.py` 的 `VALID_CATEGORIES` 目前沒有 `location`，活動地點還沒有獨立的推薦詞分類。
4. `frontend/src/views/CreateProjectView.vue` 和 `frontend/src/views/EditProjectView.vue` 的 `location` 欄位目前都是純文字輸入，沒有接推薦詞下拉。
5. `projects.py` 目前會把 group / person / budget / expense 相關資訊寫入推薦詞，但沒有把 location 一起回收。
6. `SettingsView.vue` 目前只有系統設定，沒有推薦詞編輯管理區塊。

## 預期改動

### 1. 推薦詞編輯功能補齊
- 在後端補完整推薦詞管理 API。
- 增加推薦詞的查詢、編輯、刪除能力。
- 保留現有的新增與批次新增流程，避免影響既有自動學習邏輯。
- 在資料模型層補足可管理欄位，讓前端能取得 `id / category / value / count / last_used_at` 這類管理資訊。

### 2. 地點推薦詞下拉選單
- 在 `CreateProjectView.vue` 與 `EditProjectView.vue` 的 `location` 欄位加入 datalist / autocomplete 下拉。
- 讓 location 的歷史值可以被寫回推薦詞庫。
- 新增或編輯活動時，location 仍可自由輸入，但要能快速選用既有地點。

### 3. 推薦詞來源統一
- 將 `projects.py` 的推薦詞回收流程補上 `location`。
- 讓活動資料在建立與更新時，會自動把地點寫入推薦詞庫。
- 讓建議詞的排序維持目前的 `last_used_at / count` 邏輯，避免熱門詞被洗掉。

### 4. 管理介面
- 先把「推薦詞管理」放進 `SettingsView.vue`，做成一個獨立區塊。
- 管理區塊至少要有：分類篩選、搜尋、編輯、刪除、新增。
- 如果後續表格欄位變多，再視情況拆成獨立頁面，但 v0.0.24 先不擴路由。

## 預期修改檔案

### Backend
- `backend/repositories/suggestion_repository.py`
- `backend/routers/suggestions.py`
- `backend/routers/projects.py`

### Frontend
- `frontend/src/services/api.js`
- `frontend/src/views/SettingsView.vue`
- `frontend/src/views/CreateProjectView.vue`
- `frontend/src/views/EditProjectView.vue`

## 執行步驟

1. 先補後端推薦詞 CRUD，讓管理介面有資料可用。
2. 再把 `location` 類別接進推薦詞系統。
3. 接著在 `CreateProjectView` 與 `EditProjectView` 加上地點下拉。
4. 最後在 `SettingsView` 做推薦詞編輯區塊，讓推薦詞可直接改、刪、補。

## 驗證計畫

1. 在活動建立頁輸入新地點一次後，重新開頁應能在下拉選單看到同一地點。
2. 在活動編輯頁修改地點後，推薦詞庫也會同步更新。
3. 在推薦詞管理區塊編輯既有詞彙後，前端下拉與搜尋結果會跟著變更。
4. 既有的 group / person / budget / expense 推薦詞行為不受影響。
5. 送出活動後，`location` 仍會正常寫回專案 metadata，且不破壞現有儲存流程。
