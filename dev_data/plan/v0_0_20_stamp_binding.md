# v0.0.20 實作計畫：印章綁定與自動蓋章 (Stamp Binding & Application)

本計畫旨在建立完整的印章處理鏈，支援多種角色印章、社團大章及浮貼騎縫章。在產出 PDF 憑證時，系統會自動抽取對應印章，套用隨機旋轉（±10 度），並依據設定精準蓋印。

## 決策與設定原則 (User Feedback Resolved)
1. **個人章（5 顆）**：包含「經手人章（固定蓋社長章）」、「活動總務章」、「總務組長章」、「社長章」、「指導老師章」等。**活動總務**與**總務組長**視為獨立個體，各自擁有固定、不重疊的蓋章位置，兩顆章在同一份憑證上**同時出現**。
2. **社團大章（社團關防）**：通常只有一個（若上傳多個則隨機挑選）。
3. **財務章（騎縫章）**：「與正本相符」及「已稽核」兩種章。這兩個章必須作為**騎縫章**，蓋在每張憑證（發票/收據）與底稿黏貼用紙的邊緣交界處。
4. **隨機性**：系統在產生 PDF 時給予正負 10 度的隨機旋轉；同類型印章若上傳多個（例如同一個人的章蓋了多次上傳），會隨機挑選一個以增加真實感。
5. **綁定範圍**：印章是**人的附屬品** — 每個 `Stamp` 都 FK 到 `Person` 表。因為「命名跟人走」且「一個人會上傳多個章」（用於隨機挑選增加真實感），虛擬實體也拆成**獨立的「人」**：「與正本相符」、「已稽核」、「社團關防」各自是一個虛擬 Person，這樣每個虛擬人都能掛多張不同缺陷的章來隨機抽選。
6. **資料庫重設**：本版本重設資料庫（不需要 migration），所有 Stamp/Group 舊資料會清空。

## Open Questions

*(目前無)*

---

## Proposed Changes

### 1. Database & Models (資料庫結構)

> **Note**: 本版本重設資料庫。現有 `Group` 表與 `Stamp` 表將被**替換**，不需要 migration script。

#### [DELETE] 移除舊的 `Group` 模型
- 原有的 `Group(group_name, leader_name)` 模型過於簡陋，替換為新的 `Person` 模型。

#### [NEW] 新增 `Person` 模型
```python
class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)    # 人名或虛擬實體名稱
    role = Column(String, nullable=False)                  # 角色/職位 (見下方 Enum)
    is_virtual = Column(Boolean, default=False)            # True = 公共章/社團關防等虛擬實體
    created_at = Column(Float, default=lambda: time.time())

    stamps = relationship("Stamp", back_populates="owner", cascade="all, delete-orphan")
```

**預設的 `role` 值**（可作為 Enum 或常數）：
| role key | 中文名稱 | is_virtual | 說明 |
|----------|---------|:----------:|------|
| `handler` | 經手人 | ❌ | 固定蓋社長章（後設邏輯） |
| `activity_general_affairs` | 活動總務 | ❌ | 獨立蓋章位置 |
| `general_affairs_head` | 總務組長 | ❌ | 獨立蓋章位置 |
| `president` | 社長 | ❌ | 也供「經手人」回退使用 |
| `advisor` | 指導老師 | ❌ | — |
| `fin_original` | 與正本相符 | ✅ | 虛擬實體，騎縫章，可上傳多張隨機抽選 |
| `fin_audited` | 已稽核 | ✅ | 虛擬實體，騎縫章，可上傳多張隨機抽選 |
| `club_seal` | 社團關防 | ✅ | 虛擬實體，社團大章，可上傳多張隨機抽選 |

#### [MODIFY] 修改 `Stamp` 模型
```python
class Stamp(Base):
    __tablename__ = "stamps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False)   # stamp 用途分類 (personal / fin_original / fin_audited / club)
    image_path = Column(String, nullable=False)
    created_at = Column(Float, default=lambda: time.time())

    owner = relationship("Person", back_populates="stamps")
```

**`category` 簡化為 1 種**：因為每個虛擬實體只掛一種用途的章，`category` 不再需要做細分。所有章統一為 `personal`，**蓋章位置與用途完全由 `Person.role` 決定**。

> **核心設計**：「兩顆總務章蓋在不同位置」自然成立 — 因為他們屬於不同 `role` 的 `Person`。「與正本相符」和「已稽核」各自是獨立的虛擬 Person，每個人底下可以上傳多張不同缺陷的章圖片，系統隨機抽選以避免數十頁的章缺陷完全一致。

---

### 2. Backend Repository & Service (後端 Repository & Service 層)

#### [MODIFY] `backend/repositories/stamp_repository.py`
- 移除現有的 `group_name` 相關欄位序列化。
- 新增方法：
  - `list_stamps_by_owner(owner_id: int) -> list[dict]`
  - `list_stamps_by_role(role: str) -> list[dict]` — 透過 JOIN Person 表，依 role 查詢所有可用印章。

#### [NEW] `backend/repositories/person_repository.py`
- 基本 CRUD：`list_persons()`、`get_person(id)`、`create_person()`、`delete_person()`。
- `get_or_create_virtual(role: str)` — 確保「與正本相符」「已稽核」「社團關防」三個虛擬實體存在。
- `ensure_all_virtuals()` — 系統啟動時呼叫，一次建立所有預設虛擬實體。
- `list_persons_by_role(role: str)`

#### [MODIFY] `backend/engine/stamp_service.py`
- 修改 `register_stamps`：改為接收 `owner_id` 而非 `group_name`。
- 新增「印章隨機抽取」邏輯：
  - `get_random_stamp_by_role(role: str) -> str | None` — 依 `Person.role` 隨機挑選一張印章圖片路徑。使用 `random.choice()`。因為所有 category 都是 `personal`，不再需要 `get_random_stamp_by_category`。
- **經手人章後設邏輯**：`get_handler_stamp()` — 若 `handler` role 沒有任何章，自動回退取 `president` role 的章。
- **印章缺失處理**：若某個 role 完全沒有可用印章，返回 `None`，由呼叫端決定跳過並記錄 Warning。

#### [MODIFY] `backend/routers/stamps.py`
- 更新 `StampSelection` 模型：移除 `group_name`，改為 `owner_id: int`。
- 更新 `register_stamps` endpoint。
- 新增 `GET /stamps/by-role/{role}` endpoint。

#### [NEW] `backend/routers/persons.py`
- 新增獨立的 Person 路由，處理 Person 的 CRUD：
  - `GET /persons` — 取得所有人員與虛擬實體列表（供前端下拉選單使用）。
  - `POST /persons` — 新增人員。
  - `DELETE /persons/{id}` — 刪除人員。

#### [MODIFY] `backend/routers/groups.py`
- 舊有的 Group 相關 API 暫時保留但標記 deprecated，未來版本再行移除，避免前端其他舊功能中斷。

---

### 3. Backend PDF Generation (後端 PDF 生成)

#### [MODIFY] `backend/engine/voucher_text_config.py`
- 新增 `STAMP_ZONES` 設定區塊，定義**靜態角色章**在 A4 PDF 上的蓋章位置：
  ```python
  STAMP_ZONES = {
      "handler":                    {"rect": [x0, y0, x1, y1]},  # 經手人蓋章處
      "activity_general_affairs":   {"rect": [x0, y0, x1, y1]},  # 活動總務蓋章處（固定獨立位置）
      "general_affairs_head":       {"rect": [x0, y0, x1, y1]},  # 總務組長蓋章處（固定獨立位置）
      "president":                  {"rect": [x0, y0, x1, y1]},  # 社長蓋章處
      "advisor":                    {"rect": [x0, y0, x1, y1]},  # 指導老師蓋章處
      "club_seal":                  {"rect": [x0, y0, x1, y1]},  # 社團關防位置
  }
  ```
  > **注意**：騎縫章（`fin_original`、`fin_audited`）的位置為**動態計算**，不列入 `STAMP_ZONES`，將由 `VoucherGenerator` 在運行時依每張發票圖片的邊界 (`img_rect`) 即時決定。

#### [MODIFY] `backend/engine/voucher_generator.py`
- 修改 **`generate_from_layout`**（這是實際被 `voucher.py` router 呼叫的方法，而非 `generate_voucher_pdf`）：
  - 新增 `stamps: dict[str, str | None]` 參數，接收各 role 的印章圖片路徑。
- **靜態蓋章邏輯**：
  - 遍歷 `STAMP_ZONES`，如果 `stamps[role]` 不為 `None`，將印章圖片蓋到對應的 `rect` 上。
- **實作騎縫章邏輯**：
  - 在貼上每張憑證圖片（計算出 `img_rect`）後，將 `fin_original` 和 `fin_audited` 蓋在 `img_rect` 的邊界上。**若底稿上貼了多張發票圖片，則每一張發票都需要蓋上一組騎縫章**。
- **經手人章後設邏輯**：產出憑證時，若 `handler` 的 stamp 為 `None`，系統預設取用 `president` 的印章來代替蓋印。
- **印章缺失處理**：若 PDF 產出時發現某個角色完全沒有可用圖片（例如指導老師尚未建檔），系統只會留下 Warning 日誌並**跳過該章**，不會中斷 PDF 產出流程。
- **隨機旋轉**：使用 PyMuPDF (`fitz`) 的 `insert_image` 功能，實作 **印章圖片的隨機旋轉 (Random Rotation, -10° ~ +10°)**，讓蓋章效果更自然。
- **透明通道保留**：蓋章圖片**不能**走現有的 `_image_stream_from_pil`（因為它會 `convert("RGB")` 消滅 alpha 通道），需要用獨立的 PNG bytes 路徑直接餵入 `page.insert_image(rect, stream=png_bytes)`。

#### [MODIFY] `backend/routers/voucher.py`
- **擴充 Layout Config API**：修改 `_TemplateLayoutPayload`，加入 `stampZones: dict | None`，讓前端的 `StampZoneConfigView` 可以透過 `PUT /config/template-layout` 儲存設定。
- 在 `generate_voucher_pdf` endpoint 中（第 347–433 行），在 `resolved_pages` 組裝完成之後、`generator.generate_from_layout` 呼叫之前，插入印章收集邏輯：
  ```python
  # --- 印章收集 (在 generator.generate_from_layout 之前) ---
  ALL_STAMP_ROLES = [*STAMP_ZONES.keys(), "fin_original", "fin_audited"]
  stamp_paths = {}
  for role in ALL_STAMP_ROLES:
      stamp_paths[role] = await stamp_service.get_random_stamp_by_role(role)
  ```
- 將 `stamp_paths` 傳入 `generator.generate_from_layout`。

---

### 4. Frontend — 印章管理重構 (前端)

#### [MODIFY] `frontend/src/views/StampsManagementView.vue`
- 重構印章庫管理介面：
  - 改為以 **Person（人員）** 為分組展示，每個 Person 下方展開其所有印章。
  - 虛擬實體（與正本相符、已稽核、社團關防）以特殊 UI 標識（例如不同顏色 badge）。
  - 支援「新增人員」→「為此人上傳印章」的流程。
  - 可進行預覽與刪除操作。
  - **格式驗證與提示**：在介面上明確提示使用者「印章圖片必須為**透明背景的 PNG 格式**」。

#### [MODIFY] `frontend/src/components/StampAssignDialog.vue`
- 在框選印章準備儲存時：
  - 下拉選單改為「選擇所屬人員」（從 Person 列表選擇）。
  - 隱藏舊有的 `group_name` / 自訂輸入框。

---

### 5. Frontend — 三個新獨立頁面 (前端)

#### [NEW] 頁面 A：`StampSourceUploadView.vue` — 印章圖片上傳與集體管理
- 路由：`/stamps/upload`
- 功能：
  - 上傳包含多顆印章的原始圖片（掃描圖、照片等）。
  - 在圖片上框選個別印章 → 分配給對應的 Person。
  - 集中管理已上傳的印章素材，支援批量刪除、重新分配。
  - 本頁整合現有 `StampAssignDialog` 的框選功能。

#### [NEW] 頁面 B：`VoucherStampPreviewView.vue` — PDF 產出預覽與蓋章編輯
- 路由：`/project/:id/stamp-preview`
- 功能：
  - 產出 PDF **之前**的預覽頁面，在 A4 範本上顯示所有印章的預覽位置。
  - 使用者可以看到每個角色章、騎縫章的實際蓋印位置與效果。
  - 允許微調個別印章的位置偏移（如果預設位置需要調整）。
  - 確認無誤後才正式產出 PDF。

#### [NEW] 頁面 C：`StampZoneConfigView.vue` — 預設蓋章位置設定
- 路由：`/settings/stamp-zones`
- 功能：
  - 在 A4 範本圖上，以**視覺拖拉**方式設定各角色章的預設蓋章 `rect` 位置。
  - 即時預覽：拖動框的同時顯示印章的預覽效果。
  - 設定結果寫入後端 `voucher_text_config.py` 的 `STAMP_ZONES`（或獨立的 JSON config 檔）。
  - 騎縫章的位置規則（邊界跨越比例等）也在此頁設定。

#### [MODIFY] `frontend/src/router/index.js`
- 新增以上 3 條路由。

---

## Verification Plan

### 自動測試 / 程式碼檢查
- 驗證 `Person` 與 `Stamp` 模型的 CRUD 以及 FK cascade 邏輯。
- 驗證 `get_random_stamp_by_role` 的隨機抽取邏輯。
- 驗證 `handler` 回退至 `president` 的邏輯。
- 測試 `VoucherGenerator.generate_from_layout` 能夠在計算出的 `img_rect` 邊緣正確疊加帶有旋轉參數的**透明**印章（騎縫章邏輯）。
- 確認印章圖片走 PNG 路徑（不被 `convert("RGB")` 消滅透明通道）。

### 手動測試 (Manual Verification)
1. **前端管理**：
   - 新增人員（社長、活動總務、總務組長、指導老師）並各自上傳印章。
   - 為虛擬實體「與正本相符」、「已稽核」、「社團關防」各上傳**至少 2 張**不同的印章圖片。
2. **蓋章位置設定（頁面 C）**：
   - 在 StampZoneConfigView 頁面拖拉設定各角色的蓋章 rect 位置。
3. **PDF 預覽（頁面 B）**：
   - 在 VoucherStampPreviewView 頁面確認印章預覽位置正確。
4. **自動蓋章與 PDF 匯出**：
   - 到憑證編輯器點擊「匯出憑證 PDF」。
   - 檢查產出的 PDF 每一頁底部簽章欄是否蓋滿 5 個角色章與 1 個社團大章（其中「活動總務」與「總務組長」**各自出現在獨立位置**）。
   - 重點檢查：每張貼上去的發票/收據圖片，其左/右/下邊界是否有正確跨越並蓋上「與正本相符」和「已稽核」的騎縫章。
   - 確認每次匯出時，所有印章都會產生微小的隨機旋轉。
   - 確認印章疊加處**無白底遮擋**（透明通道正常）。
   - **連續匯出兩次**，確認虛擬實體的印章圖片有被隨機抽選（非每次都同一張）。
