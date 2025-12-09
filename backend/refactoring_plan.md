# 後端重構計劃

本文件分析後端程式碼的結構問題，並提出重構建議以提高可維護性。

---

## 檔案大小與複雜度分析

| 檔案 | 行數 | 類別/函數數量 | 複雜度評估 | 建議 |
|-----|------|-------------|-----------|------|
| `managers/task_manager.py` | 454 | 22 方法 | 高 | 建議拆分 |
| `processing/receipt_splitter.py` | 415 | 9 方法 | 高 | 建議拆分 |
| `engine/export.py` | 388 | 4 方法 | 中高 | 建議拆分 |
| `routers/projects.py` | 338 | 33 路由 | 高 | 建議拆分 |
| `engine/core.py` | 242 | 21 方法 | 中 | 可維持 |
| `managers/project_crud.py` | 215 | 15 方法 | 中 | 可維持 |
| `engine/file_ops.py` | 165 | 8 方法 | 低 | 良好 |
| `managers/project_manager.py` | 118 | 14 方法 | 低 | 良好 |
| `managers/project_setup.py` | 120 | 8 方法 | 低 | 良好 |

---

## 重構建議

### 1. 拆分 `managers/task_manager.py` (454 行)

**問題**：
- 同時處理資料庫操作、狀態管理、業務邏輯
- 單一檔案過大，不易測試和維護

**建議拆分方案**：

```
managers/
├── task_manager.py          # 主要協調器 (保留)
├── job_repository.py        # 資料庫操作層 (新增)
└── job_state_machine.py     # 狀態轉換邏輯 (新增)
```

**職責劃分**：

#### `job_repository.py` - 資料存取層
- 資料庫連線管理
- CRUD 操作（insert, update, select, delete）
- 原始 SQL 查詢
- **移入方法**：
  - `_get_conn()`
  - `_init_db()`
  - `_emit_event()`
  - 所有直接操作 SQLite 的方法

#### `job_state_machine.py` - 狀態機邏輯
- Job 狀態轉換規則
- 狀態驗證
- 階段（stage）管理
- **移入方法**：
  - `complete_ocr()`
  - `complete_llm()`
  - `fail_job()`
  - `reset_and_claim()`

#### `task_manager.py` - 協調器（保留）
- 對外 API 介面
- 協調 Repository 和 StateMachine
- 高層業務邏輯
- **保留方法**：
  - `enqueue()`
  - `claim_for_ocr()` / `claim_for_llm()`
  - `get_job()` / `list_jobs()`
  - `get_job_details()` / `save_manual_text()`

---

### 2. 拆分 `processing/receipt_splitter.py` (415 行)

**問題**：
- 包含影像處理、輪廓偵測、驗證邏輯、透視變換
- 單一類別職責過多

**建議拆分方案**：

```
processing/
├── receipt_splitter.py      # 主協調器 (保留)
├── image_preprocessor.py    # 影像前處理 (新增)
├── contour_validator.py     # 輪廓驗證邏輯 (新增)
└── perspective_transform.py # 透視變換 (新增)
```

**職責劃分**：

#### `image_preprocessor.py` - 影像前處理
- 灰階化
- 雙邊濾波
- Canny 邊緣檢測
- 形態學操作

#### `contour_validator.py` - 輪廓驗證
- 角度驗證 `_validate_angles()`
- 長寬比驗證 `_validate_aspect_ratio()`
- 面積驗證
- 四邊形檢測

#### `perspective_transform.py` - 透視變換
- 點排序 `_order_points()`
- 透視變換 `_perspective_transform()`
- 去背處理

#### `receipt_splitter.py` - 主協調器（保留）
- 整合各個步驟
- 主流程 `split()` 方法
- 配置管理

---

### 3. 拆分 `engine/export.py` (388 行)

**問題**：
- Excel 匯出、專案封存、人工修正重新生成混在一起
- 每個功能都很大且獨立

**建議拆分方案**：

```
engine/
├── export_handler.py        # 整合介面 (新建)
├── excel_exporter.py        # Excel 產生 (新增)
├── archive_handler.py       # 專案封存 (新增)
└── regeneration_handler.py  # 人工修正重新生成 (新增)
```

**職責劃分**：

#### `excel_exporter.py` - Excel 匯出
- 從 jobs.db 讀取資料
- 格式化為 DataFrame
- 產生 Excel 檔案
- **移入方法**：`archive_to_excel()` 的 Excel 產生部分

#### `archive_handler.py` - 專案封存
- ZIP 打包
- 檔案複製
- 資料庫備份
- **移入方法**：`seal_project()`

#### `regeneration_handler.py` - 人工修正處理
- 讀取 Excel
- 呼叫 LLM 重新生成
- 更新 Job 狀態
- **移入方法**：`regenerate_from_archive()`

#### `export_handler.py` - 整合介面（新建）
- 提供統一的匯出 API
- 協調三個子模組
- 保持向後相容的介面

---

### 4. 拆分 `routers/projects.py` (338 行, 33 個路由)

**問題**：
- 所有 API 端點都在一個檔案
- 包含專案 CRUD、檔案操作、處理操作、Job 管理等多種職責

**建議拆分方案**：

```
routers/
├── __init__.py              # 匯總所有路由器
├── project_routes.py        # 專案 CRUD 路由
├── file_routes.py           # 檔案操作路由
├── processing_routes.py     # 處理操作路由
├── job_routes.py            # Job 管理路由
├── correction_routes.py     # 人工修正路由
└── group_routes.py          # 群組管理路由
```

**職責劃分**：

#### `project_routes.py` - 專案 CRUD
- `GET /api/projects` - 列表
- `POST /api/projects` - 建立
- `PUT /api/projects/{id}` - 更新
- `DELETE /api/projects/{id}` - 刪除
- `GET /api/projects/{id}` - 狀態查詢

#### `file_routes.py` - 檔案操作
- `POST /api/projects/{id}/add_files` - 新增檔案
- `POST /api/projects/{id}/rotate/{filename}` - 旋轉圖片
- `GET /api/projects/{id}/raw_files` - 取得原始檔案
- `DELETE /api/projects/{id}/raw_files/{filename}` - 刪除檔案

#### `processing_routes.py` - 處理操作
- `POST /api/projects/{id}/run_split` - 執行分割
- `POST /api/projects/{id}/split/{filename}` - 單檔分割
- `POST /api/projects/{id}/run_ocr` - 執行 OCR
- `POST /api/projects/{id}/run_llm` - 執行 LLM
- `POST /api/projects/{id}/run_export` - 匯出
- `POST /api/projects/{id}/run_archive` - 封存

#### `job_routes.py` - Job 管理
- `GET /api/projects/{id}/jobs` - 列出 Jobs
- `DELETE /api/projects/{id}/jobs/{job_id}` - 刪除 Job
- `POST /api/projects/{id}/jobs/{job_id}/ocr` - 單一 OCR
- `POST /api/projects/{id}/jobs/{job_id}/llm` - 單一 LLM

#### `correction_routes.py` - 人工修正
- `GET /api/projects/{id}/jobs/{job_id}/details` - 取得詳細資料
- `POST /api/projects/{id}/jobs/{job_id}/manual_text` - 儲存人工修正
- `POST /api/projects/{id}/jobs/{job_id}/regenerate` - 重新生成

#### `group_routes.py` - 群組管理
- `GET /api/groups` - 列出群組
- `POST /api/groups` - 建立群組
- `DELETE /api/groups/{name}` - 刪除群組

#### `__init__.py` - 路由匯總
```python
from fastapi import APIRouter
from . import project_routes, file_routes, processing_routes, job_routes, correction_routes, group_routes

router = APIRouter()

router.include_router(project_routes.router)
router.include_router(file_routes.router)
router.include_router(processing_routes.router)
router.include_router(job_routes.router)
router.include_router(correction_routes.router)
router.include_router(group_routes.router)
```

---

## 需要合併的檔案

### 選項 A：合併 `text_corrector.py` + `data_extractor.py` → `llm_handler.py`

**理由**：
- 這兩個類別都很小（46 行 + 56 行）
- 都只是 LLM 的薄封裝
- 都只被 `llm_handler.py` 使用

**建議**：
- 將兩者合併成 `llm_handler.py` 的內部方法
- 減少檔案數量，簡化結構

**實施方式**：
```python
# backend/processing/llm_handler.py (合併後)

class LLMHandler:
    def __init__(self, config):
        self.model_name = config["llm_settings"].get("model_name", "qwen3:1.7b")
        self.config = config
    
    def _correct_text(self, text: str) -> str:
        """原 TextCorrector.correct_text"""
        # ... 文字校正邏輯
    
    def _extract_data(self, text: str) -> dict:
        """原 DataExtractor.extract_data"""
        # ... 資料提取邏輯
    
    def structure_with_llm(self, pre_formatted_text: str) -> dict:
        corrected = self._correct_text(pre_formatted_text)
        structured = self._extract_data(corrected)
        return {
            "corrected_full_text": corrected,
            "structured_data": structured
        }
    
    def regenerate_from_corrected_text(self, corrected_text: str) -> dict:
        return self._extract_data(corrected_text)
```

### 選項 B：保持獨立（推薦）

**理由**：
- 符合單一職責原則
- 便於獨立測試
- 未來可能替換不同的校正/提取策略

**建議**：保持現狀，不合併

---

## 需要刪除的檔案

### `processing/test.py` (427 行)

**問題**：
- 這是 `receipt_splitter.py` 的完整複製品
- 程式碼 100% 重複
- 可能是開發過程中的備份

**建議**：**直接刪除**

**驗證方式**：
```bash
# 確認兩者內容相同
diff backend/processing/test.py backend/processing/receipt_splitter.py
```

---

## 實施優先順序

### 第一階段：立即執行（低風險）
1. **刪除 `processing/test.py`** - 零風險，立即收益
2. **補充測試** - 為重構提供安全網

### 第二階段：逐步重構（中風險）
3. **拆分 `routers/projects.py`** - 影響範圍明確，易於拆分
4. **拆分 `engine/export.py`** - 功能獨立，風險較低

### 第三階段：核心重構（高風險）
5. **拆分 `managers/task_manager.py`** - 核心模組，需要充分測試
6. **拆分 `processing/receipt_splitter.py`** - 影像處理邏輯複雜

---

## 重構原則

### 1. 向後相容
- 保持現有 API 介面不變
- 使用 Facade 模式提供舊介面

### 2. 逐步遷移
- 一次只重構一個模組
- 每次重構後執行完整測試

### 3. 測試優先
- 重構前補充測試
- 重構後驗證測試通過

### 4. 文件同步更新
- 更新 README.md
- 更新程式碼註解

---

## 重構後的預期結構

```
backend/
├── main.py
├── README.md
├── engine/
│   ├── core.py
│   ├── export_handler.py      # 整合介面
│   ├── excel_exporter.py      # NEW
│   ├── archive_handler.py     # NEW
│   ├── regeneration_handler.py # NEW
│   ├── file_ops.py
│   └── workers.py
├── managers/
│   ├── project_manager.py
│   ├── project_crud.py
│   ├── project_setup.py
│   ├── task_manager.py         # 簡化後
│   ├── job_repository.py       # NEW
│   └── job_state_machine.py    # NEW
├── processing/
│   ├── ocr_handler.py
│   ├── llm_handler.py
│   ├── text_corrector.py
│   ├── data_extractor.py
│   ├── receipt_splitter.py     # 簡化後
│   ├── image_preprocessor.py   # NEW
│   ├── contour_validator.py    # NEW
│   └── perspective_transform.py # NEW
├── routers/
│   ├── __init__.py             # 路由匯總
│   ├── project_routes.py       # NEW
│   ├── file_routes.py          # NEW
│   ├── processing_routes.py    # NEW
│   ├── job_routes.py           # NEW
│   ├── correction_routes.py    # NEW
│   ├── group_routes.py         # NEW
│   └── websocket.py
└── utils/
    ├── parser.py
    └── utils.py
```

---

## 測試覆蓋率目標

| 模組 | 當前覆蓋率 | 目標覆蓋率 |
|-----|----------|----------|
| `engine/` | ~60% | 80% |
| `managers/` | ~70% | 85% |
| `processing/` | ~30% | 75% |
| `routers/` | ~80% | 90% |
| `utils/` | ~50% | 90% |

---

## 估計工作量

| 任務 | 預估工時 | 風險等級 |
|-----|---------|---------|
| 刪除 test.py | 0.5 小時 | 低 |
| 拆分 projects.py | 4 小時 | 中 |
| 拆分 export.py | 6 小時 | 中 |
| 拆分 task_manager.py | 8 小時 | 高 |
| 拆分 receipt_splitter.py | 6 小時 | 高 |
| 補充測試 | 10 小時 | 低 |
| 更新文件 | 2 小時 | 低 |
| **總計** | **36.5 小時** | - |

---

## 驗收標準

### 1. 功能完整性
- [ ] 所有現有功能正常運作
- [ ] API 回應格式不變
- [ ] 資料庫結構不變

### 2. 測試通過率
- [ ] 所有單元測試通過
- [ ] 所有整合測試通過
- [ ] 新增測試覆蓋率達標

### 3. 程式碼品質
- [ ] 無 linter 錯誤
- [ ] 無循環依賴
- [ ] 單一檔案不超過 300 行

### 4. 文件更新
- [ ] README.md 反映新結構
- [ ] API 文件更新
- [ ] 重構過程記錄

---

## 風險管理

### 風險 1：破壞現有功能
- **緩解措施**：充分的測試覆蓋
- **應急計劃**：Git 分支管理，可快速回滾

### 風險 2：API 不相容
- **緩解措施**：保持所有 API 端點路徑不變
- **應急計劃**：使用 API 版本控制

### 風險 3：效能下降
- **緩解措施**：重構後進行效能測試
- **應急計劃**：保留原始實作作為備用

---

## 下一步行動

1. ✅ 撰寫此重構計劃
2. ✅ 補充單元測試
3. ⏳ **待審核**：使用者確認重構計劃
4. ⏳ 執行第一階段：刪除 test.py
5. ⏳ 執行第二階段：拆分路由和匯出模組
6. ⏳ 執行第三階段：拆分核心模組
7. ⏳ 驗證與文件更新
