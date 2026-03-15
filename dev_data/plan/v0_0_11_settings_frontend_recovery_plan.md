# V0.0.11 更新計畫 (Settings 前端修復與設定流程收斂)

日期：2026-03-15

## 1. 核心目標

V0.0.11 的目標很單純：

1. 修復目前「系統設定」前端頁面實際使用時的故障。
2. 收斂設定頁前後端契約，避免再次出現「畫面能 build，但 load/save 在 runtime 壞掉」的情況。
3. 建立足夠的回歸驗證，讓後續再改 `config.json` 或 Settings UI 時不會靜默破壞。

---

## 2. 目前已知事實

### 2.1 現況盤點

- 前端設定頁路由已存在：`/settings` → `frontend/src/views/SettingsView.vue`
- 前端目前透過：
  - `GET /api/config/` 載入設定
  - `POST /api/config/` 儲存設定
- 後端設定路由已存在：`backend/routers/config.py`
- 設定頁同時還會額外載入群組清單（`listGroups()`）並提供新增/刪除群組功能。

### 2.2 已完成的靜態驗證

- `SettingsView.vue` 與 `api.js` 無編輯器靜態錯誤。
- `npm run build` 可成功通過。
- 這表示目前問題高度可能不是編譯層，而是：
  - runtime API 契約不一致
  - 某些欄位初始化/回填流程錯誤
  - save 後 reload/遮罩 API key 行為不正確
  - 設定頁混入群組管理後，局部失敗把整頁操作體驗拖垮

---

## 3. 風險假設與優先排查方向

### P1. 設定 load/save 契約可能只覆蓋了 `vision_settings` 的一部分

- 前端只維護 `model_name`、`reasoning_effort`、`base_url`、`api_key` 四個欄位。
- 後端 `config.json` 中實際還有 `temperature`、`timeout`、`max_retries`、`model`、`debug` 等欄位。
- 雖然 router 目前採 merge 策略，但仍需驗證：
  - save 後是否會意外覆蓋掉其他欄位
  - masked API key 再送回時是否真的保留原值

### P2. 設定頁可能被非核心功能牽連

- `SettingsView.vue` 不是純設定頁，還混有群組管理與憑證範本設定入口。
- 若 `listGroups()`、`upsertGroup()`、`deleteGroup()` 任一環節失敗，目前頁面只做局部 `console.error` 或 `alert`，容易造成「使用者覺得整頁壞掉，但 build 與語法都正常」。

### P3. UX 回饋不足，導致故障難以辨識

- 目前主要使用 `alert()` 顯示錯誤。
- 缺乏欄位層級的 loading / success / error state，使用者很難分辨是：
  - 載入失敗
  - 儲存失敗
  - API key 被遮罩
  - 群組資料未載入

---

## 4. 執行策略

### Phase 1：重現與定義故障面

1. 明確重現「設定前端壞掉」的實際操作路徑。
2. 用瀏覽器 Network + console + 後端 log 鎖定是：
   - 頁面空白
   - 欄位不回填
   - 儲存無效
   - 群組區塊失效
   - API key 顯示/覆蓋異常
3. 把故障從模糊描述收斂成可驗證的單一或多個 bug。

### Phase 2：設定契約收斂

1. 明確定義前端可編輯的設定 schema。
2. 若需要，為 `/api/config/` 補上更明確的 request/response model。
3. 確保 masked API key、partial update、runtime reload 三者行為一致。
4. 若目前設定頁承載過多責任，評估把群組管理拆成獨立區塊或獨立頁面。

### Phase 3：前端穩定性修復

1. 修正 `SettingsView.vue` 的初始化與儲存流程。
2. 移除脆弱的隱式假設，改為明確的 fallback 與錯誤狀態。
3. 用較穩定的頁內提示取代單純 `alert()`，至少讓失敗原因可見。
4. 若故障根源來自 API shape mismatch，則一併修正 `frontend/src/services/api.js` 與後端 router。

### Phase 4：回歸驗證補強

1. 後端：補 `config` router 測試，覆蓋 masked key 與 merge 行為。
2. 前端：若測試基礎設施允許，補 Settings 頁載入/儲存 smoke test。
3. 至少提供一條手動驗證清單，確認：
   - 進入 `/settings` 可載入既有值
   - 修改後可成功寫回
   - API key 遮罩後不會誤清空
   - 群組區塊失敗不影響 vision settings 儲存

---

## 5. 驗收標準

完成 V0.0.11 時，需同時滿足：

1. `/settings` 頁可正常載入，不出現白屏或核心欄位空白異常。
2. Vision settings 可成功儲存並在刷新後正確回填。
3. 遮罩後的 API key 不會在再次儲存時被覆寫成 `***`。
4. 群組管理區塊即使失敗，也不會拖垮整個設定頁。
5. 至少有一組自動化測試或 smoke regression，覆蓋設定頁最核心的 load/save 路徑。

---

## 6. 非目標

本版不主動擴張到以下範圍，除非它們被證實就是 settings 故障根因：

- 大規模重做整個設定頁 UI
- 重新設計 `config.json` 全部結構
- 一次整合所有管理工具頁（例如憑證範本座標設定頁）

---

## 7. 執行備註

- 目前靜態建置通過，因此下一輪應優先從「實際操作重現」開始，而不是先盲改畫面。
- 若確認問題只在設定頁 runtime 契約，應優先做小範圍修復，避免把 V0.0.11 擴成無邊界重構。

---

## 8. 執行快照（2026-03-15）

### 8.1 已落地

1. 設定頁新增「自動抓取供應商模型列表」流程：
  - 後端新增 `GET /api/config/vision-models`
  - 前端可按鈕抓取模型並快速套用到 `model_name`
2. 群組管理改為「同組可多位組長」：
  - 保留既有資料相容
  - 新增移除單一組長的 API 與前端操作
3. 每位組長可上傳多張電子章：
  - 新增 stamps upload/list/delete/file API
  - 前端設定頁可直接管理各組長章圖
4. 憑證範本座標頁編輯體驗修正：
  - 金額格可直接編輯 `X0~X5 + Y`
  - 畫布改成範例文字可拖拉（非單點）
  - 背景圖縮放改為 Fabric 實際寬高 fit + 置中

### 8.2 已知狀態（更新）

1. 圖片相關問題：大致修復，轉為觀察項
  - 使用者回報目前「大體修好」。
  - 若再發生偏移，優先檢查 devicePixelRatio / 瀏覽器縮放 / 外層 CSS 對 canvas 寬高覆蓋。

### 8.3 下一步

1. 補一組最小可重現案例（固定 PDF + 固定座標 + 截圖比對）做回歸檢查。
2. 若再出現背景偏移，加入頁面內 debug 資訊（canvas/bg 原始尺寸、fitScale、left/top）快速定位。