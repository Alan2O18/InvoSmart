# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [V0.0.8-Phase3] - 2026-03-09

### 🎯 P3/P4 Completion: Artifact Cleanup + Focused Tests

**Phase 3 Focus**: Finish pending plan items P3 and P4.

### Added
- `tests/test_image_preprocessor.py` - Image preprocessing coverage (4 tests)
  - `preprocess` shape/type validation
  - edge detection non-zero output check
  - contour area sorting verification
  - empty image contour behavior

- `tests/test_engine_export.py` - Export facade delegation coverage (5 tests)
  - `run_excel` delegation
  - `archive_to_excel` delegation with custom filename
  - `run_word` engine requirement validation
  - `run_word` delegation with job repo from engine
  - `seal_project` delegation with flags

### Removed
- Deleted coverage artifact file: `.coverage`

### Test Metrics
- **Total Tests:** 416 → 425 (+9 tests)
- **Test Results:** 425 passed, 0 failed
- **Coverage:** 4061 statements, 630 missed (84%)

### Key Coverage Gains
- `backend/processing/image_preprocessor.py`: **56% → 100%**
- `backend/engine/export.py`: **71% → 100%**

---

## [V0.0.8-Phase2] - 2026-03-09

### 🎯 Coverage Improvement: 82% → 84%

**Phase 2 Focus**: Advanced error handling, geometric validation, and LLM edge cases

### Added

#### New Test Modules
- `tests/test_contour_validator.py` - ContourValidator geometric validation (11 tests)
  - `order_points` - Standard/rotated rectangle vertex ordering (including diamond edge case)
  - `validate_aspect_ratio` - Valid/invalid/boundary value aspect ratio checks
  - **Coverage:** contour_validator.py now at 100%

#### Extended Test Classes
- `tests/test_processing.py::TestLLMHandlerAdvanced` - LLM error handling (8 tests)
  - `call_with_thinking` - Empty content response and exception handling
  - `structure_with_llm` - Empty input and JSON parsing errors
  - `regenerate_from_corrected_text` - Text regeneration flow
  - `clean_receipt` - Success path and no-text branch
  - `init_without_ollama` - SystemError when Ollama service unavailable
  - **Discovery:** LLMHandler raises SystemError (not graceful degradation) on init failure

- `tests/test_routers_projects.py` - Projects router exception paths (6 tests)
  - Metadata parsing error handling
  - Update/delete/status exception propagation
  - Activity info update failures

- `tests/test_routers_processing.py` - Processing router error coverage (9 tests)
  - Processing/splitting/split_single exception paths
  - Excel/archive operation exceptions  
  - Word export template missing and output path errors

### Fixed
- `test_order_points_rotated` - Fixed diamond shape boundary condition using average y-coordinates
- `test_regenerate_excel` - Added missing `from unittest.mock import patch` import
- `test_structure_with_llm_empty_text` - Adjusted to expect error dict instead of empty dict
- `test_clean_receipt_success` - Fixed mock to use non-streaming Ollama API response
- Removed unused imports (pytest, MagicMock) and added PEP 8 blank line spacing

### Test Metrics
- **Total Tests:** 385 → 416 (+31 tests)
- **Test Results:** 416 passed, 0 failed
- **Execution Time:** ~22s (down from ~50s in Phase 1)
- **Coverage:** 4061 statements, 645 missed (84%)

### Module Coverage Snapshot
```
contour_validator.py       100% ⬆ (complete coverage)
perspective_transform.py   100%
prompts_config.py          100%
models.py                  100%
routers/processing.py      98% ⬆
voucher_layout_repo.py     97%
receipt_splitter.py        96%
utils/utils.py             95%
suggestion_repository.py   95%
```

### Remaining Gaps (6% to 90% target)
- **Low-coverage modules:**
  - word_exporter.py (65%) - Complex docx formatting logic
  - image_preprocessor.py (56%) - OpenCV preprocessing edge cases
  - files router (71%) - File upload/download error paths
  - export.py (71%) - Export coordination logic
  - pdf_engine.py (72%) - PDF parsing edge cases

- **Analysis:** Remaining 645 uncovered statements likely require integration tests (multi-component scenarios) rather than isolated unit tests. Diminishing returns observed beyond 84%.

### Next Phase Recommendations
1. **Integration Testing:** Multi-router workflows (upload → process → export)
2. **Image Processing:** OpenCV edge cases with real malformed images
3. **Word Export:** Complex docx template scenarios
4. **Practical Target:** 84% may be optimal for unit test coverage; remaining gaps need E2E tests

---

## [V0.0.8-Phase1] - 2026-03-09

### 🎯 Coverage Improvement: 77% → 82%

**Phase 1 Focus**: Critical backend infrastructure and worker loops

### Added

#### New Test Modules
- `tests/test_database_core.py` - Database initialization and configuration tests
  - Global DB path configuration and fallback logic
  - SQLite PRAGMA execution verification
  - Async session factory creation and basic queries
  
- `tests/test_utils_config.py` - Configuration management tests
  - Missing config file handling
  - Save/load roundtrip validation
  - Write failure error handling

- `tests/test_engine_worker_loops.py` - Background worker loop tests
  - PDF worker success and failure branches  
  - Receipt worker job completion paths
  - Image load error handling
  - Controlled queue testing helper

- `tests/test_engine_excel_exporter.py` - Excel export tests
  - VLM result to markdown text generation
  - Empty job validation
  - Main and detail sheet generation
  - Project status update verification

#### Test Coverage Enhancements
- `tests/test_routers_pdf.py`
  - Invalid PDF upload rejection (HTTP 400)
  - Download fallback to source PDF when processed version missing

### Changed

#### Bug Fixes
- **[backend/routers/pdf.py](backend/routers/pdf.py)** - Fixed invalid upload classification
  - Non-PDF uploads now correctly return HTTP 400 instead of 500
  - Added dedicated `ValueError` exception handling

### Removed

#### Obsolete Test Files
Deleted 8 empty placeholder test files:
- `tests/test_api.py`
- `tests/test_api_full.py`
- `tests/test_archive_handler.py`
- `tests/test_excel_exporter.py`
- `tests/test_file_ops.py`
- `tests/test_integration.py`
- `tests/test_manual_correction.py`
- `tests/test_workers.py`

#### Generated Artifacts
Cleaned up coverage analysis and cache files:
- Root-level coverage reports: `cov.txt`, `cov_utf8.txt`, `coverage_report.txt`, `coverage_report_utf8.txt`
- HTML coverage report: `htmlcov/`
- Annotated source files: all `backend/**/*.py,cover` files (55 files)
- Python cache: all `__pycache__/` directories
- Pytest cache: `.pytest_cache/`

### Coverage Details

#### Module-Level Improvements
| Module | Before | After | Δ |
|--------|--------|-------|---|
| `backend/database/core.py` | 35% | 91% | +56% |
| `backend/engine/excel_exporter.py` | 12% | 73% | +61% |
| `backend/engine/pdf_worker.py` | 13% | 74% | +61% |
| `backend/engine/workers.py` | 15% | 77% | +62% |
| `backend/routers/pdf.py` | 53% | 73% | +20% |
| `backend/utils/config.py` | 50% | 88% | +38% |

#### Test Results
- **Total Tests**: 385 passed
- **Backend Coverage**: 82%
- **Execution Time**: ~50s (full suite)

### Technical Notes

#### Plan Adaptation
The original V0.0.8 plan was adapted to current branch state:
- Database session lifecycle now managed in `backend/dependencies.py` rather than inline generators
- PDF router uses multipart file upload instead of base64 JSON payloads  
- Worker test file naming updated from plan assumptions

#### Repository Memory
Created `/memories/repo/coverage_plan_notes.md` to track plan vs. implementation variance.

### Next Phase

**Remaining Gap to 90% Target**: 8%

Priority modules for Phase 2:
1. `backend/engine/word_exporter.py` (65%)
2. `backend/processing/llm_handler.py` (56%)
3. `backend/processing/contour_validator.py` (52%)
4. `backend/routers/projects.py` (65%)
5. `backend/routers/processing.py` (66%)

---

## Previous Versions

See `dev_data/plan/` for archived version implementation notes.
