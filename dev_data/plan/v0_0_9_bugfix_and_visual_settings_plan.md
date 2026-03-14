# V0.0.9 更新計畫 (Bug 修復與可視化座標設定介面)

## 1. 核心目標 (Objectives)
V0.0.9 的主要目標是**清除目前編輯器中的惱人 Bug（發票縮放跳動、科目遺失、字碼溢出）**，並引入一個**全圖形化的「憑證排版與死區設定頁面」**（從獨立的 `coord_tool.html` 升級為系統一環），讓使用者（系統管理員）能直接用拖拉的方式解決文字偏移與蓋章死區問題，取代過去修改原始碼的笨重方式。

---

## 2. 待解 Bug 與應對策略 (Bug Fixes)

### 🐛 Bug 1: 拖動發票會導致大小變化
- **現象**：在 Canvas 上拖動或點擊發票圖片時，圖片比例或大小發生突變跳動。
- **解決方案**：
  - 檢查 Fabric.js 或 Vue 狀態同步機制，鎖死物件的 `scaleX` 與 `scaleY`。
  - 確保在切換或更新圖層時，保留原始注入時的 `boundingBox` 寬高比例不被意外重置。

### 🐛 Bug 2: 憑證編號只放得下四個字元 (自動縮放字體)
- **現象**：當憑證編號超過 4 個字 (如 `D-16-01`)，文字會超出版面格子。
- **解決方案 (Auto Font-Scaling)**：
  - **前端 (Canvas)**：計算目標格子的最大寬度 (Max Width)，若文字長度乘上預設字體大小超出寬度，則動態往下調降 `fontSize` 直到剛好塞入為止。
  - **後端 (PDF ReportLab)**：在寫入 PDF 時實作對等的文字寬度計算 `pdfmetrics.stringWidth()`，若過長則覆蓋參數中的字級，實現「自動縮小字體保證不超出格子」。

### 🐛 Bug 3: 預算科目仍然沒有抓出來
- **現象**：產出憑證時，「預算科目」欄位呈現空白。
- **解決方案**：追蹤 API `/api/voucher/template` 與資料庫 `project.activity_info.host_budget_item` 的映射關係，確保建立草稿物件時，正確把該欄位預設帶入 `budgetItem`。

---

## 3. 全新功能：可視化座標與死區設定頁 (Visual Settings Page)

針對問題 4 (文字小偏)、問題 5 (本地工具連動後台)、問題 7 (死區太近蹭到框線)，我們將整合 `coord_tool.html` 與 Vue 框架，打造專屬的系統設定頁：

### 🛠️ 架構設計
- **前端頁面 (`SettingsView.vue` 或 `VoucherConfigView.vue`)**：
  - 引入原 `coord_tool.html` 與 `poc_image_zoom.html` 的精華設計。
  - 支援「拖拉文字方塊」以對位（解決文字小偏）。
  - 支援「調整半透明紅色死區塊 (Dead Zone)」的高低與寬度（解決蓋章位置蹭到框線）。
- **後後 API 連動**：
  - `GET /api/config/voucher_layout`：讀取後端的 `voucher_text_config.py` 或獨立的 JSON config 檔案。
  - `PUT /api/config/voucher_layout`：保存使用者拖拉後產出的新 `(X, Y, FontSize, DeadZoneRect)` 到後端配置檔。
  - 後端 PDF 產生器改為讀取此動態配置檔，而非寫死的座標。

---

## 4. 預計使用的 AI Agent 技能 (Skills)

在此計畫的 `[EXECUTION]` 執行階段，AI 助手將主動或配合運用以下內建技能來確保程式碼品質：

1. 🎨 **`frontend-design` (前端設計極致化)**：
   - **應用場景**：用於刻劃全新的「可視化座標與死區設定頁」。確保拖拉工具列、座標屬性屬性面板 (Inspector) 以及畫布的 UI/UX 符合現代化暗色系管理後台設計，且不要看起來像廉價的 MVP。
2. ⚡ **`vueuse-functions` (Vue 組合式函式庫)**：
   - **應用場景**：在實作畫布拖拉 (Drag)、滑鼠縮放滾動 (Zoom pointer) 與邊界偵測時，直接依賴 VueUse 的 `useDraggable`, `useMouse`, `useElementBounding` 等成熟解法，取代手刻的原生 listener 事件，讓程式碼更乾淨且避免 Bug 1 (拖拉跳動) 再次發生。
3. 🐍 **`python-pro` (Python 現代開發專家)**：
   - **應用場景**：實作後端的字體寬度計算與自動縮放 (Auto Font-Scaling)，並運用 Pydantic V2 打造嚴謹的座標 Config 讀寫 API，確保使用者從網頁存回來的座標資料安全無虞。
4. 🧠 **`brainstorming` (腦力激盪)**：
   - **應用場景**：已運用此技能為本階段提煉需求、收斂「視覺工具」與「後端連動」的系統設計，並產出此計畫書。

---

## 5. 執行步驟
此為計畫藍圖，等待長官核准後切換至 `EXECUTION` 模式執行：
1. 建立設定頁 API (讀寫 JSON 配置檔)。
2. 實作 frontend `VoucherConfigView.vue` 可視化座標調整頁面。
3. 修復字體溢出與自動縮放 (前後端同步)。
4. 追蹤並連接預算科目資料綁定。
5. 解決拖動發票造成大小變異的問題。

## 附1. 原始問題
1.首先是拖動發票會導致大小變化的問題
2.是憑證編號只放得下四個的問題
3.是預算科目還是沒抓出來的問題
4.是有些文字還是小偏的問題
5. 我需要怎麼解決4.的問題呢，把原本用來本地測試位置的那個東西放上去，直接跟後台位置設定連動就可以了
6. 我需要麼解決2.的問題呢，自動縮放字體保證不超出格子
7.是有關死區設計離蓋章的位置還是有點近的問題，上端已經蹭到了框線
8. 7.跟5.一起做一個設定業面用於可視化
9.計畫中包含使用甚麼技能在.agent
10. 這是一個編號為v0.0.9的更新計畫放在plan

---

## 附2. 深度審閱：問題清單與解決方案

### ⚠️ 問題 1: Bug 2 實作方案與現有技術棧不符
**嚴重性：高 🔴**

**問題描述：**
計畫中提到使用 ReportLab 的 `pdfmetrics.stringWidth()` 實現字體寬度計算，但審查代碼發現：
- 當前系統使用 **PyMuPDF (fitz)** 作為 PDF 處理引擎，而非 ReportLab
- `voucher_generator.py` 已有 `insert_textbox` 機制，具備動態調降字體的能力（見 `_insert_purpose` 方法）
- 引入 ReportLab 會增加依賴複雜度且與現有架構不一致

**解決方案：**
- **前端 (Canvas)**：
  - 使用 Canvas 2D API 的 `measureText(text).width` 計算文字寬度
  - 若超出目標寬度，迭代降低 `fontSize` 直到符合（類似 `_insert_purpose` 的邏輯）
  
- **後端 (PyMuPDF)**：
  - **擴展** `_insert_named_text` 方法，加入 `maxWidth` 參數
  - 使用 PyMuPDF 的 `page.get_textbox()` 或試寫法 (trial rendering) 測量文字寬度
  - 範例實作骨架：
    ```python
    def _insert_named_text_with_autoscale(self, page, field_name, text, max_width=None):
        config = self.text_field_config[field_name]
        fontsize = int(config["fontSize"])
        min_fontsize = int(config.get("minFontSize", 10))
        
        if max_width:
            # Trial rendering to measure actual width
            with fitz.open() as scratch:
                scratch_page = scratch.new_page()
                for fs in range(fontsize, min_fontsize - 1, -1):
                    rect = scratch_page.insert_text(
                        (0, 0), text, fontsize=fs, 
                        fontname="F0" if self.font_path else "helv",
                        fontfile=self.font_path if self.font_path else None
                    )
                    if rect.width <= max_width:
                        fontsize = fs
                        break
        
        self._insert_text(page, tuple(config["point"]), text, fontsize=fontsize)
    ```

**執行步驟修正：**
- 第 3 步改為：「實作字體自動縮放（基於 PyMuPDF 試寫法）」
- 增加子步驟：「前端使用 Canvas measureText API 同步實現預覽效果」

---

### ⚠️ 問題 2: Bug 3 資料欄位映射路徑不明確
**嚴重性：中 🟠**

**問題描述：**
計畫提到「追蹤 API `/api/voucher/template` 與資料庫 `project.activity_info.host_budget_item`」，但：
- 審查代碼未找到 `host_budget_item` 欄位定義
- `activity_info` 在 `project` 表中的結構未明確
- 不清楚預算科目應該從哪個 router 或 repository 獲取

**解決方案：**
1. **資料庫結構核查：**
   - 檢查 `backend/database/models.py` 中 `Project` model 的 `activity_info` JSON 欄位內應包含哪些鍵
   - 若無 `host_budget_item`，需明確應使用 `budget_category` 或其他替代欄位

2. **API 注入點確認：**
   - 在 `GET /{project_id}/template` 端點中，從 `project.activity_info` 提取預算科目
   - 修改回傳的 `projectMeta` 加入 `budgetItem` 欄位
   - 範例修正：
     ```python
     activity_info = project.get("activity_info") or {}
     budget_item = activity_info.get("budget_category", "")  # 或正確的鍵名
     
     return {
         "projectMeta": {
             "budgetItem": budget_item,  # 新增此欄位
             # ... 其他欄位
         }
     }
     ```

3. **前端接收驗證：**
   - `VoucherEditorView.vue` 在接收 template 時，確保 `projectMeta.budgetItem` 有預設填入草稿

**執行步驟修正：**
- 第 4 步拆分為：
  1. 「確認資料庫 activity_info 結構與預算科目欄位名稱」
  2. 「修改 GET /template API 注入 budgetItem」
  3. 「前端驗證欄位綁定與預覽」

---

### ⚠️ 問題 3: API 端點設計與現有路由衝突
**嚴重性：中 🟠**

**問題描述：**
計畫提出：
- `GET /api/config/voucher_layout`
- `PUT /api/config/voucher_layout`

但現有系統已有：
- `GET /api/voucher/{project_id}/layout`
- `POST /api/voucher/{project_id}/layout`

兩套路由設計存在語義混淆：
- `/config/voucher_layout` 暗示全局系統配置（template 層級的座標定義）
- `/{project_id}/layout` 是專案級的憑證排版（已填寫的表單數據）

**解決方案：**
明確區分兩種配置層級：

1. **全局範本配置** (新增)：
   - `GET /api/config/voucher-template-coords` - 讀取範本座標與死區設定
   - `PUT /api/config/voucher-template-coords` - 保存管理員調整的座標
   - 後端檔案：`backend/data/voucher_template_config.json`（替代寫死在 `voucher_text_config.py`）

2. **專案憑證排版** (既有)：
   - 保持 `/{project_id}/layout` 不變
   - 這是使用者編輯後的憑證內容（非座標定義）

3. **新增 Router 方法：**
   ```python
   @router.get("/config/template-coords")
   async def get_template_coords():
       config_path = PROJECT_ROOT / "backend" / "data" / "voucher_template_config.json"
       if not config_path.exists():
           # Fallback to hardcoded TEXT_FIELD_CONFIG
           return get_text_field_config()
       with open(config_path, "r", encoding="utf-8") as f:
           return json.load(f)
   
   @router.put("/config/template-coords")
   async def save_template_coords(payload: dict):
       config_path = PROJECT_ROOT / "backend" / "data" / "voucher_template_config.json"
       config_path.parent.mkdir(exist_ok=True)
       with open(config_path, "w", encoding="utf-8") as f:
           json.dump(payload, f, ensure_ascii=False, indent=2)
       return {"status": "saved"}
   ```

**執行步驟修正：**
- 第 1 步細化為：
  - 「新增全局範本座標 API (`/config/template-coords`，GET/PUT)」
  - 「VoucherGenerator 改為從 JSON 配置檔讀取座標（Fallback 到硬編碼）」

---

### ⚠️ 問題 4: 前端頁面命名衝突與路由規劃缺失
**嚴重性：中 🟠**

**問題描述：**
- 計畫提到「`SettingsView.vue` 或 `VoucherConfigView.vue`」
- 但審查發現 `SettingsView.vue` 已存在且用於 VLM 與群組管理設定
- 計畫未提供路由路徑（如 `/voucher-config`）與導航入口

**解決方案：**
1. **新建獨立頁面：**
   - 檔名：`frontend/src/views/VoucherTemplateConfigView.vue`
   - 路由：`/voucher-template-config`

2. **路由註冊：**
   ```javascript
   // router/index.js
   {
     path: '/voucher-template-config',
     name: 'VoucherTemplateConfig',
     component: () => import('@/views/VoucherTemplateConfigView.vue'),
     meta: { requiresAuth: true, title: '憑證範本座標設定' }
   }
   ```

3. **導航入口：**
   - 在現有 `SettingsView.vue` 中增加「憑證範本設定」卡片連結
   - 或在 NavBar 增加「管理員工具」下拉選單

4. **權限控制：**
   - 確保只有管理員角色可訪問此頁面（避免一般使用者誤改全局配置）

**執行步驟修正：**
- 第 2 步修改為：「建立 VoucherTemplateConfigView.vue 並註冊路由」
- 增加子步驟：「在 SettingsView 增加跳轉入口」

---

### ⚠️ 問題 5: 死區 (Dead Zone) 資料結構未定義
**嚴重性：中 🟠**

**問題描述：**
計畫提到「調整半透明紅色死區塊」，但未說明：
- 死區在配置檔案中如何表示（矩形？多邊形？）
- 前端畫布如何渲染死區（Canvas 疊層？Fabric 物件？）
- 後端 PDF 生成器如何避開死區（僅影響 UI 還是實際排版？）

**解決方案：**
1. **資料結構定義：**
   ```typescript
   // TypeScript 介面
   interface DeadZone {
     name: string          // 如 "stamp_area"
     rect: [number, number, number, number]  // [x, y, width, height]
     color?: string        // 可選顏色，預設 "rgba(255, 0, 0, 0.2)"
     description?: string  // 如 "蓋章位置，避免圖片遮擋"
   }
   
   interface VoucherTemplateConfig {
     textFields: { ... },
     deadZones: DeadZone[]
   }
   ```

2. **前端渲染方案：**
   - 使用 `coord_tool.html` 中的 `.dead-zone` CSS 類別
   - 或在 Fabric Canvas 上加入不可移動的半透明矩形物件
   - 範例（原生 div 覆蓋）：
     ```vue
     <div v-for="zone in deadZones" :key="zone.name"
          class="dead-zone"
          :style="{
            left: zone.rect[0] + 'px',
            top: zone.rect[1] + 'px',
            width: zone.rect[2] + 'px',
            height: zone.rect[3] + 'px',
            background: zone.color || 'rgba(255, 0, 0, 0.2)'
          }">
     </div>
     ```

3. **拖拉調整實作：**
   - 使用 VueUse 的 `useDraggable` + `useResizable`（需自行實作 resize handles）
   - 或使用 Fabric.js 的 Rect 物件並標記為 `selectable: true, movable: true`

4. **後端影響說明：**
   - **若僅為 UI 輔助**：後端無需處理，僅前端顯示提醒
   - **若影響排版**：在 `VoucherGenerator._paste_images()` 中增加死區衝突檢測

**執行步驟修正：**
- 第 2 步增加子任務：「定義 DeadZone 資料結構與渲染邏輯」
- 第 7 步（原問題 7）細化為：「調整死區預設矩形參數避免蹭框」

---

### ⚠️ 問題 6: Bug 1 根因分析不足
**嚴重性：中 🟠**

**問題描述：**
計畫提到「鎖死 scaleX/scaleY」，但未說明：
- 跳動發生在哪個事件（`object:moving`？`selection:created`？頁面切換？）
- 是圖片物件還是整個 Canvas viewport 的縮放問題
- `PdfWorkbench.vue` 中 Fabric 物件的初始化是否正確保留比例

**解決方案：**
1. **診斷步驟：**
   - 在 `PdfWorkbench.vue` 的 Fabric 事件中加入 console.log 追蹤：
     ```javascript
     fabricCanvas.value.on('object:moving', (e) => {
       console.log('[DEBUG] Moving:', e.target.scaleX, e.target.scaleY)
     })
     fabricCanvas.value.on('object:scaling', (e) => {
       console.log('[DEBUG] Scaling:', e.target.scaleX, e.target.scaleY)
     })
     ```

2. **鎖定縮放：**
   - 若確認是使用者意外觸發縮放，禁用 Fabric 物件的縮放控制：
     ```javascript
     const img = new fabric.Image(imgElement, {
       scaleX: initialScale,
       scaleY: initialScale,
       lockScalingX: true,  // 🔒 禁止 X 軸縮放
       lockScalingY: true,  // 🔒 禁止 Y 軸縮放
       hasControls: true,
       hasBorders: true
     })
     ```

3. **保留狀態持久化：**
   - 確保 `pageStamps.value[pageNum]` 保存時包含完整的 scale 值
   - 在恢復物件時強制覆蓋：
     ```javascript
     fabric.util.enlivenObjects([objData]).then(([fabricObj]) => {
       fabricObj.set({ scaleX: objData.scaleX, scaleY: objData.scaleY })
       fabricCanvas.value.add(fabricObj)
     })
     ```

**執行步驟修正：**
- 第 5 步改為：
  1. 「診斷 Fabric 事件中 scale 值變化時機」
  2. 「禁用圖片 scale 控制或鎖定比例」
  3. 「驗證跨頁面切換時 scale 保持不變」

---

### ⚠️ 問題 7: 配置檔案遷移策略缺失
**嚴重性：低 🟡**

**問題描述：**
計畫提到「後端 PDF 產生器改為讀取動態配置檔」，但未說明：
- 現有使用 `voucher_text_config.py` 硬編碼的系統如何平滑遷移
- JSON 配置檔與硬編碼同時存在時的優先級
- 若 JSON 檔案損壞或缺失，是否有降級方案

**解決方案：**
1. **Fallback 機制：**
   ```python
   def get_text_field_config():
       config_path = Path(__file__).parent.parent / "data" / "voucher_template_config.json"
       if config_path.exists():
           try:
               with open(config_path, "r", encoding="utf-8") as f:
                   custom_config = json.load(f)
               logger.info("使用自訂座標配置: %s", config_path)
               return custom_config
           except Exception as e:
               logger.warning("讀取配置檔失敗，使用預設值: %s", e)
       
       # Fallback to hardcoded TEXT_FIELD_CONFIG
       return deepcopy(TEXT_FIELD_CONFIG)
   ```

2. **配置檔驗證：**
   - 使用 Pydantic V2 定義 Schema 驗證 JSON 結構
   - 範例：
     ```python
     from pydantic import BaseModel, Field
     
     class TextFieldConfig(BaseModel):
         type: str
         point: tuple[float, float] | None = None
         fontSize: int
         maxChars: int | None = None
         # ... 其他欄位
     
     class VoucherTemplateConfigSchema(BaseModel):
         textFields: dict[str, TextFieldConfig]
         deadZones: list[dict] = Field(default_factory=list)
     ```

3. **初次啟動遷移：**
   - 在首次運行時，若 JSON 不存在，自動從 `TEXT_FIELD_CONFIG` 生成預設檔案

**執行步驟修正：**
- 第 1 步增加：「實作 Fallback 機制與 Pydantic 驗證 Schema」

---

### ⚠️ 問題 8: 前端技術選型風險
**嚴重性：低 🟡**

**問題描述：**
計畫提到使用 VueUse 的 `useDraggable` 取代原 Fabric.js 拖拉，但：
- `useDraggable` 適用於 DOM 元素拖拉，而 Fabric.js 是 Canvas 物件拖拉
- 兩者不在同一渲染層，混用可能導致座標系轉換複雜
- `coord_tool.html` 使用原生 DOM + `onmousedown`，與 Fabric.js 架構不同

**解決方案：**
1. **技術棧統一建議：**
   - **選項 A（推薦）**：憑證編輯器繼續使用 Fabric.js（已有成熟實作）
   - **選項 B**：座標設定頁使用純 DOM + VueUse（類似 `coord_tool.html`）
   - **避免**：在同一頁面混用 Fabric + VueUse 拖拉

2. **實際應用分配：**
   - **VoucherEditorView.vue**：保持 Fabric.js 處理圖片與印章拖拉
   - **VoucherTemplateConfigView.vue**：使用 VueUse + 原生 DOM 處理座標設定
     - 背景圖：`<img>` 標籤顯示範本 PNG
     - 文字框：`<div class="text-item">` + `useDraggable`
     - 死區：`<div class="dead-zone">` + `useDraggable` + resize handles

3. **VueUse 使用範例：**
   ```vue
   <script setup>
   import { ref } from 'vue'
   import { useDraggable } from '@vueuse/core'
   
   const el = ref(null)
   const { x, y, style } = useDraggable(el, {
     initialValue: { x: 100, y: 100 },
     onEnd: (position) => {
       // 保存座標到配置
       updateFieldConfig('voucherNo', { point: [position.x, position.y] })
     }
   })
   </script>
   
   <template>
     <div ref="el" :style="style" class="text-item draggable">
       憑證編號
     </div>
   </template>
   ```

**執行步驟修正：**
- 第 2 步明確：「VoucherTemplateConfigView 使用 VueUse + DOM（非 Fabric）」
- 第 4 步刪除「避免 Bug 1 再次發生」的說法（不同頁面不相關）

---

### ⚠️ 問題 9: 執行步驟缺少驗收標準
**嚴重性：低 🟡**

**問題描述：**
計畫的執行步驟僅列出任務名稱，未提供：
- 每個步驟的完成定義 (Definition of Done)
- 測試驗證方式
- 回歸測試範圍

**解決方案：**
為每個執行步驟增加驗收標準（AC）：

1. **步驟 1：建立設定頁 API**
   - ✅ AC1: `GET /api/voucher/config/template-coords` 返回完整配置
   - ✅ AC2: `PUT` 保存後重新 GET 能取得相同數據
   - ✅ AC3: JSON 檔案不存在時自動返回硬編碼預設值
   - 測試：使用 Postman/httpie 測試 API

2. **步驟 2：實作 VoucherTemplateConfigView.vue**
   - ✅ AC1: 頁面顯示範本 PNG 底圖
   - ✅ AC2: 可拖拉文字框並即時更新座標數值
   - ✅ AC3: 死區塊可調整大小與位置
   - ✅ AC4: 點擊「保存」後呼叫 PUT API
   - 測試：手動 E2E 測試拖拉與保存

3. **步驟 3：修復字體溢出與自動縮放**
   - ✅ AC1: 憑證編號 `D-16-01` 在前端預覽完整顯示
   - ✅ AC2: 生成 PDF 後，憑證編號字體自動縮小至適配
   - ✅ AC3: 極端情況（10 字元）不會超出格子
   - 測試：生成測試憑證並檢視 PDF

4. **步驟 4：追蹤並連接預算科目資料綁定**
   - ✅ AC1: `GET /template` 返回 `projectMeta.budgetItem` 欄位
   - ✅ AC2: 前端自動填入預算科目至草稿
   - ✅ AC3: 生成 PDF 後預算科目欄位有值
   - 測試：建立新專案並驗證完整流程

5. **步驟 5：解決拖動發票造成大小變異**
   - ✅ AC1: 拖動圖片時 scale 值不變
   - ✅ AC2: 切換頁面後圖片大小保持一致
   - ✅ AC3: 旋轉或移動後重新選取不會跳動
   - 測試：在 VoucherEditorView 操作 10 次無異常

**執行步驟修正：**
- 每個步驟下新增「驗收標準 (Acceptance Criteria)」子章節

---

### ✅ 問題 10: 缺少回滾計畫與風險緩解
**嚴重性：低 🟡**

**問題描述：**
若上線後發現問題，計畫未提供：
- 如何回滾到舊版本
- 配置檔案變更是否向下兼容
- 資料庫遷移是否可逆

**解決方案：**
增加「風險管理與回滾策略」章節：

1. **配置檔案兼容性：**
   - 新版 JSON 配置與舊版 `voucher_text_config.py` 並行（Fallback 機制）
   - 確保未更新 JSON 的情況下，系統使用原硬編碼配置

2. **資料庫變更：**
   - 若新增 `activity_info.budget_category` 欄位，使用 Alembic migration
   - Migration 需支援 `upgrade` 與 `downgrade`

3. **前端回滾：**
   - 保留 `VoucherEditorView.vue` 舊版邏輯（使用 feature flag 控制新功能）
   - 範例：
     ```javascript
     const enableAutoFontScale = ref(false) // 可從 config API 動態控制
     ```

4. **回滾步驟：**
   - 若新功能異常，刪除 `voucher_template_config.json` 即自動回退到硬編碼
   - Git revert 前端 commit
   - 資料庫執行 `alembic downgrade -1`（若有 migration）

---

### 📋 修訂後的執行步驟（第 5 節建議替換版本）

此為計畫藍圖，等待長官核准後切換至 `EXECUTION` 模式執行：

**Phase 1: 後端基礎架構 (2-3 天)**
1. ✅ 建立全局範本座標 API
   - 新增 `GET/PUT /api/voucher/config/template-coords`
   - 實作 Fallback 機制（JSON → 硬編碼）
   - 增加 Pydantic Schema 驗證
   - **驗收：** Postman 測試 GET/PUT 往返一致性

2. ✅ 實作字體自動縮放（PyMuPDF 版本）
   - 擴展 `_insert_named_text_with_autoscale` 方法
   - 前端使用 Canvas `measureText` 同步預覽
   - **驗收：** 憑證編號 `D-16-01` 與 10 字元極端測試

**Phase 2: 前端座標設定頁 (3-4 天)**
3. ✅ 建立 VoucherTemplateConfigView.vue
   - 路由註冊 `/voucher-template-config`
   - 使用 VueUse `useDraggable` 實作文字框拖拉
   - 渲染死區塊（可調整大小）
   - 整合 `coord_tool.html` 的 UI 設計
   - **驗收：** 拖拉後保存，重新載入座標正確

4. ✅ 在 SettingsView 增加導航入口
   - 新增「憑證範本設定」卡片
   - 增加權限控制（管理員限定）

**Phase 3: Bug 修復 (2 天)**
5. ✅ 修復預算科目空白問題
   - 確認 `activity_info` 中預算科目欄位名稱
   - 修改 `GET /{project_id}/template` 注入 `budgetItem`
   - 前端驗證綁定
   - **驗收：** 生成 PDF 後預算科目欄位有值

6. ✅ 解決 Fabric.js 拖動跳動
   - 診斷 scale 變化事件
   - 鎖定 `lockScalingX/Y` 屬性
   - 驗證跨頁面狀態持久化
   - **驗收：** 操作 10 次無跳動

**Phase 4: 整合測試與部署 (1-2 天)**
7. ✅ 端到端測試
   - 調整座標 → 生成憑證 → 驗證對位
   - 調整死區 → 確認蓋章位置不蹭框
   - 長憑證編號測試

8. ✅ 撰寫更新文檔與操作手冊
   - 管理員如何使用座標設定頁
   - 配置檔案格式說明
   - 回滾步驟文檔

---

### 🎯 額外建議

1. **增加單元測試：**
   - `test_voucher_generator.py` 增加字體自動縮放測試
   - 前端增加 `VoucherTemplateConfigView.spec.js` 測試拖拉邏輯

2. **性能優化：**
   - 座標設定頁使用防抖 (debounce) 減少 API 呼叫頻率
   - JSON 配置檔增加快取機制

3. **使用者體驗：**
   - 座標設定頁增加「重置為預設值」按鈕
   - 拖拉時顯示即時座標提示 (Tooltip)
   - 增加「預覽模式」直接在設定頁看到憑證效果

---

### 📊 問題嚴重性統計

| 嚴重性 | 數量 | 問題編號 |
|--------|------|----------|
| 🔴 高   | 1    | #1 (技術棧不符) |
| 🟠 中   | 5    | #2, #3, #4, #5, #6 |
| 🟡 低   | 4    | #7, #8, #9, #10 |

**總結：** 計畫整體方向正確，但需在技術實作細節、API 設計、資料結構定義等方面進行明確化。建議按照修訂後的執行步驟逐步推進，並在每個 Phase 完成後進行 Review。

---

## 附3. 二次審閱：依最新需求修正後的問題清單與可執行方案

本附錄用於**覆蓋附錄2中已被新資訊推翻或需要收斂的部分**。本次二次審閱以以下三個新前提為準：

1. **預算科目**的業務意義不是 `activity_info.host_budget_item`，而是「這張憑證使用哪個組別的錢」，因此應直接取 `project.metadata.group` 相關欄位。
2. 可視化座標設定頁既然要正式 Vue 化，**整體統一使用 Fabric.js**，不要再分裂成 Fabric 與 DOM/VueUse 兩種拖拉模型。
3. **死區不是單純視覺紅框**，而是「發票不能放上去的區域」；也就是說它必須同時具備**顯示**與**碰撞限制**兩個責任。

### 修正 1: 預算科目的來源應改為 `project.metadata.group`
**嚴重性：高 🔴**

**二次審閱發現：**
- `CreateProjectView.vue` 建立專案時，已將 `group` 寫入 `metadata`
- `EditProjectView.vue` 編輯專案時，也直接讀寫 `metadata.group`
- `ProjectRepository.get_project()` 回傳的是 `metadata`
- 目前沒有證據顯示系統存在穩定可用的 `activity_info.host_budget_item`

**代表附錄2的問題：**
- 附錄2把預算科目的來源導向 `activity_info`，這在現況下是錯誤方向
- 若照附錄2執行，會多做一層不存在的資料追蹤，造成錯誤設計

**正確方案：**
1. `GET /api/voucher/{project_id}/template` 直接從 `project.metadata` 取值
2. 採用以下優先順序產出 `budgetItem`：
    - `metadata.group`
    - `metadata.group_name`
    - `""`
3. `VoucherEditorView.vue` 初次載入模板時，若頁面草稿中的 `budgetItem` 為空，則自動填入 `projectMeta.budgetItem`

**建議實作：**
```python
project = await engine.project_repo.get_project(project_id)
metadata = project.get("metadata") or {}
budget_item = metadata.get("group") or metadata.get("group_name") or ""

return {
      "templatePng": template_png,
      "projectMeta": {
            "id": project.get("project_id"),
            "name": project.get("name") or project.get("project_id"),
            "createdAt": project.get("created_at"),
            "budgetItem": budget_item,
      },
      "invoices": invoices,
}
```

**驗收標準：**
- 新建專案時指定 `group=餐食組`
- 進入 VoucherEditor 後，空白頁的 `budgetItem` 自動顯示 `餐食組`
- 產出 PDF 時 `budgetItem` 欄位不再空白

---

### 修正 2: 技術棧應全面統一為 Fabric.js，附錄2的 VueUse 方案作廢
**嚴重性：高 🔴**

**二次審閱發現：**
- `VoucherEditorView.vue` 已完整使用 Fabric.js
- 既有畫布物件、預覽文字、發票圖片、可拖拉元素都建立在 Fabric 上
- 若新頁面改用 VueUse + DOM，未來會產生兩套座標模型、兩套拖曳邏輯、兩套碰撞修正邏輯

**因此附錄2以下內容應視為作廢：**
- `VoucherTemplateConfigView` 使用 VueUse + DOM
- 使用 `useDraggable` / `useResizable` 作為主要拖拉模型

**正確方案：**
1. 新頁面 `VoucherTemplateConfigView.vue` 仍使用 Fabric Canvas
2. 直接重用或抽取 `VoucherEditorView.vue` 中的下列能力：
    - 底圖載入
    - 座標物件建立
    - 移動/縮放事件
    - 邊界約束
    - 序列化保存
3. 將共通邏輯抽到：
    - `frontend/src/utils/voucherCanvasConfig.js`
    - 或 `frontend/src/composables/useVoucherFabricCanvas.js`

**可執行重構方向：**
- 不從 `coord_tool.html` 原封不動搬進 Vue
- 而是「提煉互動需求」後，用 Fabric 在 Vue 中重建

**建議抽象層：**
```javascript
createTextAnchorObject(fieldKey, config)
createBlockedZoneObject(zoneKey, rect)
applyMovementConstraint(obj, layoutConfig)
serializeTemplateLayout(canvas)
deserializeTemplateLayout(canvas, payload)
```

**驗收標準：**
- 設定頁與憑證編輯頁都只依賴 Fabric
- 不新增第二套 DOM 拖拉框架
- 共用函式至少被兩個頁面使用

---

### 修正 3: 「死區」應建模為禁止放置區，不是只有顯示顏色
**嚴重性：高 🔴**

**二次審閱發現：**
- 你補充的需求是「發票拖不過去」
- 這表示死區本質是**行為約束**，不是純視覺標記
- 現有 `VoucherEditorView.vue` 已經存在 `SAFE_ZONE` 與 `clampImageRect()`，本質上就是限制發票只能待在允許區域

**因此計畫需要修正：**
- 不應把死區描述成「半透明紅色塊」本身就是核心功能
- 顏色只是輔助視覺，真正需求是**碰撞後退 / 邊界夾制**

**正確資料模型：**
```json
{
   "safeZone": { "x0": 30, "y0": 394, "x1": 565, "y1": 730 },
   "blockedZones": [
      {
         "key": "stamp_top",
         "rect": [430, 390, 120, 48],
         "label": "蓋章區",
         "visible": true
      }
   ]
}
```

**互動規則：**
1. 發票必須落在 `safeZone` 內
2. 發票不得與任一 `blockedZones` 相交
3. 拖動時若碰撞：
    - 可選擇「即時回推」
    - 或「放開時回退到上個合法位置」

**建議採用：放開時回退到最後合法位置**
- 原因：行為更穩定，使用者感受比即時抖動修正更好

**Fabric 實作方向：**
```javascript
obj.on('moving', () => {
   const nextRect = getObjectRect(obj)
   if (intersectsBlockedZone(nextRect, layout.blockedZones)) {
      restoreLastValidPosition(obj)
      return
   }
   clampIntoSafeZone(obj, layout.safeZone)
   rememberLastValidPosition(obj)
})
```

**驗收標準：**
- 發票無法被拖進蓋章區
- 蓋章區可見性可切換，但限制仍有效
- 調整死區後立即影響拖拉限制

---

### 修正 4: 這不是「從零建立新工具」，而是把既有 VoucherEditor 的能力配置化
**嚴重性：中 🟠**

**二次審閱發現：**
- 現有編輯器已具備以下能力：
   - 模板 PNG 載入
   - 發票圖片拖拉
   - `SAFE_ZONE` 視覺框
   - `clampImageRect()` 邊界約束
   - 文字預覽繪製
   - 自動排版
- 若計畫把新頁面當作獨立新工具重做，會重複造輪子

**正確方案：**
1. 將目前 `VoucherEditorView.vue` 中「與頁面草稿無關、與模板配置有關」的邏輯抽出
2. 新的配置頁只操作：
    - 文字欄位 anchor / rect
    - 字級 / 最小字級
    - safe zone
    - blocked zones
3. 舊的 VoucherEditor 則只負責：
    - 專案發票佈局
    - 套用配置後的實際預覽與輸出

**重構邊界建議：**
- `VoucherEditorView` 管「專案內容」
- `VoucherTemplateConfigView` 管「範本規則」
- 共用同一份 `voucher_template_config.json`

---

### 修正 5: API 路徑應收斂到 `/api/voucher/*`，不要再分散到 `/api/config/*`
**嚴重性：中 🟠**

**二次審閱發現：**
- 現有憑證相關 API 都已經掛在 `/api/voucher`
   - `/fonts/kaiu.ttf`
   - `/text-config`
   - `/{project_id}/template`
   - `/{project_id}/layout`
- 若把配置頁 API 放到 `/api/config`，語意上會切裂憑證領域

**正確方案：**
- 新 API 保持在 voucher router 之下
- 建議命名：
   - `GET /api/voucher/config/template-layout`
   - `PUT /api/voucher/config/template-layout`

**原因：**
1. 路由語意一致
2. 前端 service 模組可集中在 voucher API
3. 未來若要加 template preview / reset default / import export，也能同 router 演進

---

### 修正 6: 計畫中的「管理員權限」是假設，不是現成能力
**嚴重性：中 🟠**

**二次審閱發現：**
- 目前 `frontend/src/router/index.js` 沒有 `requiresAuth` 或角色守衛
- 沒看到現成登入、角色、session、admin middleware 的證據

**代表的風險：**
- 若計畫把「只有管理員可使用」當既有條件，實作時會卡住
- 權限系統本身就可能變成額外一個子專案

**正確方案：**
1. **V0.0.9 不做完整 RBAC**
2. 先採「低成本入口控制」：
    - 只從 `SettingsView` 提供進入連結
    - 在頁面明示「範本級設定，請由維護者操作」
3. 若後續真的要權限化，再列為 V0.1.0 的獨立工作項

**執行修正：**
- 把附錄2中的 `requiresAuth: true` 改成「預留 meta，不作為 V0.0.9 交付前置條件」

---

### 修正 7: 字體自動縮放不能只改後端，前端預覽也必須水平一致
**嚴重性：中 🟠**

**二次審閱發現：**
- 目前前端已有 `purpose` 的多行縮字邏輯
- 但 `voucherNo` / `budgetItem` 預覽仍是一般 `fabric.Text`
- `backend/engine/voucher_text_config.py` 裡 `voucherNo` 目前沒有 `maxWidth` 與 `minFontSize` 類設定

**風險：**
- 若只修 PDF 生成器，前端預覽仍可能看起來正常或異常，但輸出結果不同步
- 使用者會以為位置對了，實際 PDF 卻縮字或換行不同

**正確方案：**
1. 對 `voucherNo`、`budgetItem` 增加配置欄位：
    - `maxWidth`
    - `minFontSize`
    - `autoScale: true`
2. 前端預覽建立 `fabric.Textbox` 或基於測寬函式動態算字級
3. 後端生成使用同一份配置套用 autoscale

**建議配置：**
```python
"voucherNo": {
      "type": "text",
      "point": [78.5, 255],
      "fontSize": 16,
      "minFontSize": 10,
      "maxWidth": 58,
      "autoScale": True
}
```

**驗收標準：**
- `D-16-01` 不溢出
- `D-16-0010` 仍不溢出
- 前端預覽與 PDF 輸出字級差異不超過 1pt

---

### 修正 8: 配置檔不應只有 textFields，還要覆蓋 safe zone / blocked zones / preview
**嚴重性：中 🟠**

**二次審閱發現：**
- 現有硬編碼分散在：
   - `voucher_text_config.py` 的 `TEXT_FIELD_CONFIG`
   - `VoucherEditorView.vue` 的 `SAFE_ZONE`
- 若只把文字欄位存成 JSON，死區與安全區仍會留在前端硬編碼，計畫就不完整

**正確配置 Schema：**
```json
{
   "font": { "family": "VoucherKaiU", "url": "/api/voucher/fonts/kaiu.ttf" },
   "textFields": {},
   "safeZone": { "x0": 30, "y0": 394, "x1": 565, "y1": 730 },
   "blockedZones": [],
   "preview": {
      "showSafeZone": true,
      "showBlockedZones": true
   }
}
```

**執行修正：**
- `VoucherEditorView.vue` 讀取 template config 後，以 config 覆蓋本地 `SAFE_ZONE`
- 不再把 `SAFE_ZONE` 永久寫死在前端常數

---

### 修正 9: 真正的拖動跳動風險在「moving 時重算 scale + clamp」
**嚴重性：中 🟠**

**二次審閱發現：**
- `applyObjectBounds()` 會在約束時重新計算 `uniformScale`
- 若 moving / modified / load restore 的時序處理不一致，就可能造成你描述的「拖一下大小就變」
- 這個問題比單純 `lockScalingX/Y` 更接近根因

**正確方案：**
1. 把「移動限制」與「縮放限制」分成兩條路徑
2. `object:moving` 只修 `left/top`，**不要重算 scale**
3. `object:scaling` 才處理縮放與比例修正
4. 新增 `lastValidRect` 快照，避免 moving 時反覆把尺寸洗掉

**實作原則：**
```javascript
onMoving => clampPositionOnly(obj)
onScaling => normalizeScaleAndClamp(obj)
onModified => persistRect(obj)
```

**這一點很重要：**
- 目前計畫把 Bug 1 簡化成「鎖死 scaleX/scaleY」不夠精準
- 正確做法是先分離 event responsibility，再看是否需要鎖縮放

---

### 修正 10: 執行順序還要再調整，先修共用配置，再修 UI
**嚴重性：低 🟡**

**二次審閱發現：**
- 若先做設定頁 UI，再定配置格式，後面一定要回改前端與後端
- 目前最穩的順序應是先把 config schema 定好，再讓兩個頁面共用

**最終建議執行順序：**

**Phase A: 配置核心**
1. 定義 `voucher_template_config.json` schema
2. 支援 `textFields + safeZone + blockedZones + preview`
3. `voucher_text_config.py` 實作 JSON fallback

**Phase B: 後端 API**
4. 新增 `GET/PUT /api/voucher/config/template-layout`
5. `GET /api/voucher/{project_id}/template` 注入 `projectMeta.budgetItem`

**Phase C: 既有編輯器修 bug**
6. 修 `VoucherEditorView` 的 moving/scaling 跳動問題
7. 把 `SAFE_ZONE` 改成讀 config
8. 把 blocked zone 套入發票禁止放置邏輯

**Phase D: 新的設定頁**
9. 建立 `VoucherTemplateConfigView.vue`
10. 用 Fabric 編輯文字欄位與 blocked zones
11. 保存後立即可被 VoucherEditor 讀取

**Phase E: 輸出一致性**
12. 前後端同步實作 `voucherNo`/`budgetItem` autoscale
13. 補齊 PDF 與前端預覽一致性測試

---

### 附錄3 結論

第二次審閱後，這份計畫有三個必須立即修正的核心方向：

1. **預算科目不是 activity_info 問題，而是 metadata.group 映射問題。**
2. **設定頁與編輯器都應統一使用 Fabric，避免雙軌前端架構。**
3. **死區要被當成「禁止放置規則」來做，而不是只畫一塊紅色區域。**

若依附錄3 修正後再進入 EXECUTION，這份 V0.0.9 計畫才算真正達到「可直接開工、且不會中途推翻重做」的程度。