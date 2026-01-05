# Backend 測試計畫 (Testing Plan)

本文件說明 Backend 現有測試覆蓋情況，並規劃需要補充的測試項目。

---

## 環境設置

依照 [quickstart.md](./quickstart.md) 進行環境設置：

```bash
# 啟用虛擬環境
micromamba activate OCR_GA

# 執行所有測試
pytest tests/ -v

# 執行特定測試檔案
pytest tests/test_processing.py -v

# 執行特定測試類別
pytest tests/test_processing.py::TestLLMHandler -v

# 執行含有特定名稱的測試
pytest tests/ -k "keyword" -v

# 顯示測試覆蓋率
pytest tests/ --cov=backend --cov-report=term-missing
```

---

## 現有測試概覽

| 測試檔案 | 測試目標 | 狀態 |
|----------|----------|------|
| `test_api.py` | API 端點單元測試 | ✅ 已完成 (25+ tests) |
| `test_api_full.py` | 完整 API 流程測試 | ⚠️ 1 failed (`test_06_run_ocr`) |
| `test_processing.py` | OCR/LLM 處理模組 | ✅ 已完成 (15+ tests) |
| `test_engine.py` | Engine 核心功能 | ✅ 已完成 (20+ tests) |
| `test_utils.py` | 工具函數 | ✅ 已完成 (9 tests) |
| `test_manual_correction.py` | 人工修正流程 | ✅ 已完成 (4 tests) |
| `test_integration.py` | 整合測試 | ✅ 已完成 (5 tests) |

### 最近測試結果

根據 `pytest_result.txt`：
- **通過**: 30 tests
- **失敗**: 1 test (`test_api_full.py::TestBackendAPI::test_06_run_ocr`)
- **失敗原因**: `AttributeError: module 'backend.engine.core' does not have the attribute 'start_cpu_worker'`

---

## 測試覆蓋分析

### ✅ 已有良好覆蓋的模組

| 模組 | 測試檔案 | 覆蓋測試 |
|------|----------|----------|
| `backend/main.py` | `test_api.py` | API 端點測試 |
| `backend/engine/core.py` | `test_engine.py` | 專案管理、檔案操作、處理流程 |
| `backend/processing/ocr_handler.py` | `test_processing.py` | 排版重建 |
| `backend/processing/llm_handler.py` | `test_processing.py` | 文字校正、資料提取 |
| `backend/processing/receipt_splitter.py` | `test_processing.py` | 點排序、角度驗證、寬高比 |
| `backend/utils/parser.py` | `test_utils.py` | 結構化資料提取 |
| `backend/utils/utils.py` | `test_utils.py` | 中文路徑圖片讀寫 |
| `backend/managers/task_manager.py` | `test_manual_correction.py` | 狀態管理、人工修正 |

### ⚠️ 缺少測試的關鍵模組

| 模組 | 功能 | 優先級 |
|------|------|--------|
| `processing/keyword_classifier.py` | 收據類型分類 | 🔴 高 |
| `processing/qr_handler.py` | 電子發票 QR Code 解碼 | 🔴 高 |
| `processing/rapidocr_handler.py` | RapidOCR 文字識別 | 🟡 中 |
| `processing/vision_handler.py` | VLM 視覺識別 | 🟡 中 |
| `processing/audit_handler.py` | 稽核處理器 | 🟡 中 |
| `processing/receipt_processor.py` | 完整收據處理管線 | 🔴 高 |
| `managers/job_repository.py` | Job 資料存取層 | 🟡 中 |
| `managers/job_state_machine.py` | Job 狀態機邏輯 | 🟡 中 |
| `engine/workers.py` | Worker 主迴圈 | 🟢 低 |

---

## TODO: 新增測試計畫

### Phase 1: 關鍵業務邏輯測試 (高優先級)

#### 1.1 KeywordClassifier 測試 (`tests/test_classifier.py`)

```python
class TestKeywordClassifier:
    """關鍵字分類器測試"""
    
    # 電子發票分類測試
    test_classify_electronic_invoice_with_keywords()
    test_classify_electronic_invoice_with_qr_code()
    test_classify_electronic_invoice_with_pattern()
    
    # 手寫收據分類測試
    test_classify_handwritten_receipt()
    test_classify_handwritten_with_chinese_numbers()
    
    # 其他收據分類測試
    test_classify_taxi_receipt()
    test_classify_traditional_invoice()
    
    # 邊界情況測試
    test_classify_empty_text()
    test_classify_ambiguous_text()
```

**測試重點**：
- [ ] 電子發票關鍵字匹配（電子發票、載具、愛心碼）
- [ ] 電子發票格式匹配（AB-12345678）
- [ ] QR Code 強特徵判斷
- [ ] 手寫收據關鍵字（免用統一發票、大寫中文數字）
- [ ] 其他收據關鍵字（計程車、乘車證明）
- [ ] 空輸入處理
- [ ] 信心度計算正確性

---

#### 1.2 QRHandler 測試 (`tests/test_qr_handler.py`)

```python
class TestQRHandler:
    """QR Code 解碼器測試"""
    
    # 解析格式測試
    test_parse_taiwan_einvoice_qr_valid()
    test_parse_taiwan_einvoice_qr_invalid_length()
    test_parse_taiwan_einvoice_qr_invalid_format()
    
    # 日期轉換測試
    test_parse_date_conversion_republic_to_ad()
    
    # 金額解析測試
    test_parse_amount_hex_to_decimal()
    
    # 錯誤處理測試
    test_detect_and_decode_no_qr_in_image()
    test_detect_and_decode_corrupted_qr()
```

**測試重點**：
- [ ] 發票號碼解析（位置 0-9）
- [ ] 民國日期轉西元（位置 10-16）
- [ ] 十六進位金額轉十進位（位置 29-36）
- [ ] 賣方統編解析（位置 17-24）
- [ ] 無效格式錯誤處理
- [ ] 無 QR Code 圖片處理

---

#### 1.3 ReceiptProcessor 測試 (`tests/test_receipt_processor.py`)

```python
class TestReceiptProcessorV2:
    """收據處理器 v2 測試"""
    
    # 完整流程測試
    test_process_electronic_invoice()
    test_process_handwritten_receipt()
    test_process_other_receipt()
    
    # 錯誤處理測試
    test_process_invalid_image()
    test_process_empty_ocr_result()
    
    # 結果格式測試
    test_result_follows_json_schema()
    test_result_includes_ocr_stats()
    test_result_includes_llm_stats()
```

**測試重點**：
- [ ] 電子發票處理流程（OCR → 分類 → QR → 結果）
- [ ] 手寫收據處理流程（OCR → 分類 → VLM → 結果）
- [ ] 其他收據處理流程（OCR → 分類 → LLM → 結果）
- [ ] 結果格式符合 `json_schema.md` 規範
- [ ] OCR/LLM 統計資訊正確返回
- [ ] 錯誤結果格式正確

---

### Phase 2: 資料層與狀態管理測試 (中優先級)

#### 2.1 JobRepository 測試 (`tests/test_job_repository.py`)

```python
class TestJobRepository:
    """Job 資料存取層測試"""
    
    # CRUD 操作測試
    test_insert_job()
    test_get_job_existing()
    test_get_job_not_found()
    test_update_job_single_field()
    test_update_job_multiple_fields()
    test_delete_job()
    
    # 查詢測試
    test_list_jobs_all()
    test_list_jobs_by_status()
    test_count_jobs_by_status()
    test_find_claimable_job()
    
    # 事件記錄測試
    test_emit_event()
    
    # 過期任務處理
    test_mark_stale_as_failed()
```

**測試重點**：
- [ ] SQLite 連線和初始化
- [ ] Job 插入與更新
- [ ] JSON 欄位序列化/反序列化
- [ ] 狀態篩選查詢
- [ ] 可領取任務查詢邏輯
- [ ] 過期任務標記邏輯

---

#### 2.2 JobStateMachine 測試 (`tests/test_job_state_machine.py`)

```python
class TestJobStateMachine:
    """Job 狀態機測試"""
    
    # OCR 階段測試
    test_claim_for_ocr_success()
    test_claim_for_ocr_no_available_job()
    test_complete_ocr_advance_to_llm()
    test_complete_ocr_no_advance()
    
    # LLM 階段測試
    test_claim_for_llm_success()
    test_complete_llm_mark_final()
    
    # 重設與重試測試
    test_reset_and_claim_for_rerun()
    
    # 失敗處理測試
    test_fail_job()
```

**測試重點**：
- [ ] OCR 任務領取邏輯（status: ready → running）
- [ ] OCR 完成後自動進入 LLM 階段
- [ ] LLM 任務領取邏輯
- [ ] 任務完成標記為 done
- [ ] 重跑任務的重設邏輯
- [ ] 失敗任務處理

---

### Phase 3: 處理器單元測試 (中優先級)

#### 3.1 RapidOCRHandler 測試 (`tests/test_rapidocr_handler.py`)

```python
class TestRapidOCRHandler:
    """RapidOCR 處理器測試"""
    
    test_do_ocr_returns_structured_result()
    test_do_ocr_returns_stats()
    test_to_plain_text_line_ordering()
    test_get_high_confidence_text()
    test_extract_numbers()
    test_empty_image_handling()
```

**測試重點**：
- [ ] OCR 結果格式（text, box, confidence）
- [ ] 統計資訊格式（engine, total_time_s, text_blocks_count）
- [ ] 文字行排序邏輯（Y 座標 → X 座標）
- [ ] 信心度過濾
- [ ] 數字提取功能

---

#### 3.2 VisionHandler 測試 (`tests/test_vision_handler.py`)

```python
class TestVisionHandler:
    """VLM 視覺處理器測試"""
    
    test_encode_image_to_base64()
    test_process_handwritten_returns_tuple()
    test_image_to_markdown_calls_process_handwritten()
    test_clean_json_response_removes_fence()
    test_describe_image_custom_prompt()
```

**測試重點**：
- [ ] 圖片 Base64 編碼
- [ ] 返回格式（result_text, stats_dict）
- [ ] JSON 回應清理（移除 ```json）
- [ ] 統計資訊記錄

---

#### 3.3 AuditHandler 測試 (`tests/test_audit_handler.py`)

```python
class TestAuditHandler:
    """稽核處理器測試"""
    
    test_audit_electronic_matches_qr()
    test_audit_electronic_finds_discrepancy()
    test_audit_traditional_cross_validates()
    test_quick_validate_amount_match()
    test_quick_validate_amount_mismatch()
    test_parse_json_response_valid()
    test_parse_json_response_invalid()
```

**測試重點**：
- [ ] 電子發票稽核（VLM 結果 vs QR Code）
- [ ] 傳統發票交叉驗證（VLM vs RapidOCR）
- [ ] 金額快速驗證
- [ ] JSON 回應解析
- [ ] 修正套用邏輯

---

### Phase 4: 修復失敗測試

#### 4.1 修復 `test_api_full.py::TestBackendAPI::test_06_run_ocr`

**問題**: `AttributeError: module 'backend.engine.core' does not have the attribute 'start_cpu_worker'`

**解決方案**:
1. 更新測試中的 mock 路徑，改用新架構的 function names
2. 或移除過時的 `start_cpu_worker` 引用，改用 `global_receipt_worker_loop`

```python
# 舊程式碼
with patch("backend.engine.core.start_cpu_worker") as mock_worker:
    ...

# 新程式碼
with patch("backend.engine.workers.global_receipt_worker_loop") as mock_worker:
    ...
```

---

## 測試 Fixtures 規劃

### 需要新增的 Fixtures (in `conftest.py`)

```python
@pytest.fixture
def mock_rapidocr():
    """Mock RapidOCR for testing."""
    mock = MagicMock()
    mock.do_ocr.return_value = (
        [{"text": "測試文字", "box": [[0,0], [100,0], [100,30], [0,30]], "confidence": 0.95}],
        {"engine": "rapidocr", "total_time_s": 0.1, "text_blocks_count": 1}
    )
    return mock

@pytest.fixture
def mock_vision_handler():
    """Mock VisionHandler for testing."""
    mock = MagicMock()
    mock.process_handwritten.return_value = (
        '{"header": {"supplier": "Test"}, "items": []}',
        {"tokens_per_second": 50.0, "eval_count": 100}
    )
    return mock

@pytest.fixture
def mock_qr_handler():
    """Mock QRHandler for testing."""
    mock = MagicMock()
    mock.detect_and_decode.return_value = {
        "invoice_number": "AB12345678",
        "date": "2024-01-15",
        "total": 100,
        "seller_id": "12345678"
    }
    return mock

@pytest.fixture
def sample_electronic_invoice_image():
    """Create a sample image for testing."""
    import numpy as np
    return np.zeros((100, 100, 3), dtype=np.uint8)

@pytest.fixture
def temp_project_with_jobs(temp_workspace, test_engine):
    """Create a temporary project with pre-populated jobs."""
    project_id = "test_project"
    test_engine.create_project(project_id, [], name="Test Project")
    tm = test_engine.get_task_manager(project_id)
    job_id = tm.enqueue("/fake/image.jpg", stage="ocr")
    return {"engine": test_engine, "project_id": project_id, "tm": tm, "job_id": job_id}
```

---

## 執行計畫

### 優先順序

| Phase | Scope | 預估時間 | 交付項目 |
|-------|-------|----------|----------|
| 1 | 關鍵業務邏輯 | 2-3 小時 | `test_classifier.py`, `test_qr_handler.py`, `test_receipt_processor.py` |
| 2 | 資料層與狀態管理 | 1-2 小時 | `test_job_repository.py`, `test_job_state_machine.py` |
| 3 | 處理器單元測試 | 2-3 小時 | `test_rapidocr_handler.py`, `test_vision_handler.py`, `test_audit_handler.py` |
| 4 | 修復失敗測試 | 30 分鐘 | 更新 `test_api_full.py` |

### 驗證標準

- [ ] 所有測試通過 (`pytest tests/ -v`)
- [ ] 測試覆蓋率 ≥ 80% (`pytest --cov=backend`)
- [ ] 無 mock leak 或資源未釋放問題
- [ ] 測試可在 CI/CD 環境中獨立運行

---

## 相關文件

- [quickstart.md](./quickstart.md) - 環境設置指南
- [api_reference.md](./api_reference.md) - API 參考文檔
- [json_schema.md](./json_schema.md) - JSON 格式規範
- [backend_architecture.md](./backend_architecture.md) - 後端架構說明

## 2025-12-20 Work Log
- Completed Phase 1: Key Business Logic tests.
- Created tests/test_classifier.py (12 passed)
- Created tests/test_qr_handler.py (7 passed)
- Created tests/test_receipt_processor.py (5 passed)
- Completed Phase 2: Data Layer tests.
- Created tests/test_job_repository.py (11 passed)
- Created tests/test_job_state_machine.py (8 passed)
- Completed Phase 3: Processor Unit tests.
- Created tests/test_rapidocr_handler.py (6 passed)
- Created tests/test_vision_handler.py (5 passed)
- Created tests/test_audit_handler.py (5 passed)
