# 實作計畫 - 印章管理系統 (v0.0.15)

此計畫概述了印章管理系統的開發。這項功能旨在解決頻繁在憑證上手動貼圖、去背印章的痛點，建立一個數位的「印章庫 (Stamp Repository)」。使用者可以上傳包含多個印章的圖紙，系統會自動偵測、去背並切分印章，然後讓使用者分配給特定的職位或社團。

## 核心設計決策 (Design Decisions)

1. **🔴 去背 (透明背景, P0)**：為防印章遮擋憑證內容，預先使用 OpenCV 進行去背。將紅色主體保留，其餘背景轉為透明 (Alpha channel)，並統一以 `PNG` 格式儲存。
2. **🟡 紅色過濾偵測與切換 (P1)**：預設以 HSV 色域分離紅色並尋找輪廓做自動框選。針對非紅色印章（如黑色稽核章），在前端 UI 增加「模式切換」功能，切換為傳統邊緣偵測模式。
3. **🟡 手動框選備案 (P1)**：若印章蓋得太淡、彼此重疊，導致自動偵測失敗，前端 UI 提供手動圈選框作為備案。
4. **🟢 資料庫關聯策劃 (P2)**：印章類別預設使用字串存放（如「稽核」、「出納」），但也預留一個 `Group` 的外部鍵 (`group_name`) 欄位（允許 null）。這樣在未來需要把印章與社團群組打通時，無需更動架構。

## 預計修改項目

### 資料庫層 (Database Layer)

#### [MODIFY] [models.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/database/models.py)
- 新增 `Stamp` 模型：
  - `id` (Integer, 主鍵)
  - `name` (String, 不可為空)：印章名稱，例如「美術社社章」
  - `category` (String, 不可為空)：印章類型標籤，例如「社團」、「稽核」、「校長」
  - `group_name` (String, Foreign Key -> `Group.group_name`, 可為空)：未來預留給社團打通的關聯欄位
  - `image_path` (String, 不可為空)：自動去背並裁切後的 `PNG` 檔案相對路徑
  - `created_at` (Float)：建立時間

### 後端邏輯 (Backend Logic)

#### [NEW] [stamp_processor.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/processing/stamp_processor.py)
- 實作 `StampProcessor` 類別：
  - `detect_stamps(image, mode="red")`：
    - `red` 模式：使用 HSV 過濾紅色範圍，找出紅色輪廓並回傳 Bounding Boxes。
    - `edge` 模式：使用傳統 Canny Edge 邊緣偵測尋找非紅色印章。
  - `crop_and_remove_background(image, rect, mode="red")`：根據框選範圍裁切圖片，並將非印章主體 (白色或淺色背景) 加上 Alpha 通道轉為透明 PNG。

#### [NEW] [stamps.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/routers/stamps.py)
- `GET /stamps`：列出所有已儲存的印章。
- `POST /stamps/detect`：接收上傳的印章圖紙、`mode` (紅章/黑章)，回傳偵測結果（邊界框與預覽）。
- `POST /stamps/register`：接收選定框好的印章清單與 meta data，呼叫去背邏輯，將 `PNG` 存檔至 `backend/data/stamps/` 並寫入資料庫。
- `DELETE /stamps/{id}`：刪除印章資料及實體圖片。

#### [MODIFY] [main.py](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/backend/main.py)
- 註冊 `stamps` router。
- 新增靜態資源分享 (Static File Serving) 到 `backend/data/stamps/`。

### 前端介面 (Vue 3)

#### [NEW] [StampsManagementView.vue](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/views/StampsManagementView.vue)
- 印章專屬的管理 Dashboard，使用 Grid 排版展示所有印章。

#### [NEW] [StampAssignDialog.vue](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/components/StampAssignDialog.vue)
- **步驟 1 - 上傳與模式選擇**：上傳整張的印章圖紙，選擇「紅色印章」或「黑色印章」(連動後端的 `mode`)。
- **步驟 2 - 智慧框選與手動微調**：顯示預覽圖與自動產生的邊界框。允許點選項目的「取消選取」，或使用滑鼠拖拉手動新增自訂邊界框。
- **步驟 3 - 編輯屬性**：為準備存檔的每個框設定 `name` 和 `category`，確認無誤後提交儲存。

#### [NEW] [stamp.js](file:///c:/Users/tange/Desktop/all_project/py%20for%20NKNU%20GA/AI_AGENT_LAB/frontend/src/store/stamp.js)
- Pinia Store，封裝 `/stamps` API 串接邏輯與狀態管理。

## 驗證計畫 (Verification Plan)

### 自動化測試
- 為 `stamp_processor.py` 撰寫單元測試以確保在特定閾值下能正確過濾帶有白底的紅印章。

### 手動驗證流程
1. 準備一張包含數個紅色職章與一個黑色印章的 A4 畫面。
2. 開啟對話框，選擇「紅色模式」，確認系統只抓到紅色印章且不包含黑章。
3. 清除重來，嘗試手動框出黑章，並輸入名稱儲存。
4. 在 Stamps 管理介面檢查印章圖片，確保呈現去背透明效果 (Alpha 通道生效)。
