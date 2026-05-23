# 專案全檔案盤點 (2026-03-15)

本資料夾用來盤點目前工作區中「所有檔案」的用途、模組方法與架構對照。

## 產出內容

- `all_files_inventory.txt`
  - 全專案檔案快照清單 (共 7269 筆，排除 `.git` 與 `__pycache__`)
- `top_level_counts.md`
  - 以頂層模組統計檔案數
- `backend_submodule_counts.md`
  - Backend 子模組檔案數統計
- `frontend_submodule_counts.md`
  - Frontend 子模組檔案數統計
- `python_symbols_inventory.txt`
  - Python `class` / `def` 宣告索引
- `python_symbols_count_by_file.md`
  - Python 檔案的方法/類別數統計
- `frontend_symbols_inventory.txt`
  - Frontend 函式/方法樣式宣告索引
- `frontend_symbols_count_by_file.md`
  - Frontend 檔案的方法/函式數統計
- `module_method_inventory.md`
  - 依模組分類，說明各檔案在做什麼與主要方法用途
- `architecture_alignment.md`
  - Mermaid 架構圖與「現階段文件」對照結果

## 如何閱讀

1. 先看 `module_method_inventory.md` 了解模組責任與方法用途。
2. 要看「全部檔案」請直接開 `all_files_inventory.txt`。
3. 要核對架構是否對上現行文件，請看 `architecture_alignment.md`。

## 盤點範圍說明

- 已涵蓋工作區全部檔案清單。
- 其中 `frontend/node_modules` 佔 6476 筆，屬於第三方依賴；業務程式碼主要在 `frontend/src`、`backend`、`scripts`、`tests`。
- 方法索引採「宣告掃描」方式產出，用於快速導覽，不等於完整靜態分析結果。
