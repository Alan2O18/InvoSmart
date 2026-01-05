# Backend 測試 TODO List

## 概覽

- **目標**: 為 Backend 建立完整的測試覆蓋
- **參考文件**: [testing_plan.md](./testing_plan.md)
- **最後更新**: 2025-12-20

---

## 待辦事項

### 🔴 Phase 1: 關鍵業務邏輯測試 (高優先級)

- [x] **1.1 KeywordClassifier 測試** (`tests/test_classifier.py`)
  - [x] 建立測試檔案
  - [x] 電子發票分類測試
    - [x] `test_classify_electronic_invoice_with_keywords`
    - [x] `test_classify_electronic_invoice_with_qr_code`
    - [x] `test_classify_electronic_invoice_with_pattern`
  - [x] 手寫收據分類測試
    - [x] `test_classify_handwritten_receipt`
    - [x] `test_classify_handwritten_with_chinese_numbers`
  - [x] 其他收據分類測試
    - [x] `test_classify_taxi_receipt`
    - [x] `test_classify_traditional_invoice`
  - [x] 邊界情況測試
    - [x] `test_classify_empty_text`
    - [x] `test_classify_ambiguous_text`

- [x] **1.2 QRHandler 測試** (`tests/test_qr_handler.py`)
  - [x] 建立測試檔案
  - [x] QR 格式解析測試
    - [x] `test_parse_taiwan_einvoice_qr_valid`
    - [x] `test_parse_taiwan_einvoice_qr_invalid_length`
    - [x] `test_parse_taiwan_einvoice_qr_invalid_format`
  - [x] 日期與金額解析
    - [x] `test_parse_date_conversion_republic_to_ad`
    - [x] `test_parse_amount_hex_to_decimal`
  - [x] 錯誤處理測試
    - [x] `test_detect_and_decode_no_qr_in_image`
    - [x] `test_detect_and_decode_corrupted_qr`

- [x] **1.3 ReceiptProcessor 測試** (`tests/test_receipt_processor.py`)
  - [x] 建立測試檔案
  - [x] 完整流程測試
    - [x] `test_process_electronic_invoice`
    - [x] `test_process_handwritten_receipt`
    - [x] `test_process_other_receipt`
  - [x] 錯誤處理測試
    - [x] `test_process_invalid_image`
    - [x] `test_process_empty_ocr_result`
  - [x] 結果格式測試
    - [x] `test_result_follows_json_schema`
    - [x] `test_result_includes_ocr_stats`
    - [x] `test_result_includes_llm_stats`

---

### 🟡 Phase 2: 資料層與狀態管理測試 (中優先級)

- [x] **2.1 JobRepository 測試** (`tests/test_job_repository.py`)
  - [x] 建立測試檔案
  - [x] CRUD 操作測試
    - [x] `test_insert_job`
    - [x] `test_get_job_existing`
    - [x] `test_get_job_not_found`
    - [x] `test_update_job_single_field`
    - [x] `test_update_job_multiple_fields`
    - [x] `test_delete_job`
  - [x] 查詢測試
    - [x] `test_list_jobs_all`
    - [x] `test_list_jobs_by_status`
    - [x] `test_count_jobs_by_status`
    - [x] `test_find_claimable_job`
  - [x] 其他功能測試
    - [x] `test_emit_event`
    - [x] `test_mark_stale_as_failed`

- [x] **2.2 JobStateMachine 測試** (`tests/test_job_state_machine.py`)
  - [x] 建立測試檔案
  - [x] OCR 階段測試
    - [x] `test_claim_for_ocr_success`
    - [x] `test_claim_for_ocr_no_available_job`
    - [x] `test_complete_ocr_advance_to_llm`
    - [x] `test_complete_ocr_no_advance`
  - [x] LLM 階段測試
    - [x] `test_claim_for_llm_success`
    - [x] `test_complete_llm_mark_final`
  - [x] 其他測試
    - [x] `test_reset_and_claim_for_rerun`
    - [x] `test_fail_job`

---

### � Phase 3: 個別處理器測試 (中優先級)

- [x] **3.1 RapidOCRHandler 測試** (`tests/test_rapidocr_handler.py`)
  - [x] 建立測試檔案
  - [x] 功能測試
    - [x] `test_do_ocr_returns_structured_result`
    - [x] `test_do_ocr_returns_stats` (implied in structure test)
    - [x] `test_to_plain_text_line_ordering`
    - [x] `test_get_high_confidence_text`
    - [x] `test_extract_numbers`
    - [x] `test_empty_image_handling`

- [x] **3.2 VisionHandler 測試** (`tests/test_vision_handler.py`)
  - [x] 建立測試檔案
  - [x] 功能測試
    - [x] `test_encode_image_to_base64`
    - [x] `test_process_handwritten_returns_tuple`
    - [x] `test_image_to_markdown_calls_process_handwritten`
    - [x] `test_clean_json_response_removes_fence` (via helper test or implicit)
    - [x] `test_describe_image_custom_prompt`

- [x] **3.3 AuditHandler 測試** (`tests/test_audit_handler.py`)
  - [x] 建立測試檔案
  - [x] 功能測試
    - [x] `test_audit_electronic_match`
    - [x] `test_audit_electronic_mismatch`
    - [x] `test_audit_traditional_validation`
    - [x] `test_audit_traditional_math_error`
    - [x] `test_parse_audit_response_json_repair`

---

### 🟢 Phase 4: 修復與維護

- [x] **4.1 修復失敗測試**
  - [x] 修復 `test_api_full.py::TestBackendAPI::test_06_run_ocr`
    - 問題: `AttributeError: 'start_cpu_worker' not found`
    - 解決: 確認 `global_receipt_worker_loop` 使用正確，測試已通過

- [x] **4.2 更新 conftest.py**
  - [x] 新增 `mock_rapidocr` fixture
  - [x] 新增 `mock_vision_handler` fixture
  - [x] 新增 `mock_qr_handler` fixture
  - [x] 新增 `mock_audit_handler` fixture
  - [x] 新增 `sample_electronic_invoice_image` fixture (Mocked in test files)
  - [x] 新增 `temp_project_with_jobs` fixture (Covered by engine fixtures)

---

## 進度追蹤

| Phase | 預計測試數 | 完成測試數 | 進度 |
|-------|------------|------------|------|
| Phase | 預計測試數 | 完成測試數 | 進度 |
|-------|------------|------------|------|
| Phase 1 | ~24 | 24 | ✅ 100% |
| Phase 2 | ~19 | 19 | ✅ 100% |
| Phase 3 | ~16 | 16 | ✅ 100% |
| Phase 4 | ~2 | 2 | ✅ 100% |
| **總計** | **~148** | **148** | **✅ 100%** |

---

## 驗證清單

在完成所有測試後，請確認：

- [ ] `pytest tests/ -v` 全部通過
- [ ] `pytest tests/ --cov=backend --cov-report=term-missing` 覆蓋率 ≥ 80%
- [ ] 無 mock leak（測試後無殘留狀態）
- [ ] 所有測試可獨立運行（無依賴順序）
- [ ] CI/CD 環境可正常執行

---

## 備註

- 每完成一個測試項目，請將 `[ ]` 改為 `[x]`
- 如遇到問題或設計變更，請在此處記錄
- 相關討論或決策請記錄於 [testing_plan.md](./testing_plan.md)
