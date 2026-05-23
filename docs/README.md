# 📚 AI Agent Lab 文件中心 (Documentation Portal)

歡迎來到 AI Agent Lab 的文件中心。本專案採用 **VLM-First 架構**，完全解耦了傳統 OCR 流程。為了方便開發者快速上手並理解系統架構，我們對所有文檔進行了模組化分工。

請根據您的需求，查閱下方對應的指南與規格說明。

---

## 🗺️ 文檔地圖與分工指引

| 文檔類別 | 建議閱讀對象 | 文件名稱與連結 | 核心說明的職責範圍 |
| :--- | :--- | :--- | :--- |
| **🚀 開發入門** | 新加入的開發者 / 部署人員 | [🚀 快速開始 (quickstart.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/quickstart.md) | 說明如何建立 Python 虛擬環境、前端與後端的啟動步驟，以及初次運行的驗證方法。 |
| **🏗️ 系統架構** | 系統設計師 / 後端開發者 | [📐 後端架構設計 (backend_architecture.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/backend_architecture.md) | 詳細定義後端的 **三層邊界強制規則**（Router / Engine / Repository / Processing），嚴格隔離 `cv2`/`numpy`/`fitz` 的外部依賴。 |
| **⚙️ 工作流水線** | 後端開發者 / VLM 調整員 | [⚡ 處理流水線 (pipeline.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/pipeline.md) | 說明發票上傳、切分、VLM 視覺辨識、Word/PDF 生成的完整工作流。 |
| **💾 資料規格** | 資料庫管理員 / 全端開發者 | [🗄️ 資料庫結構 (database.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/database.md) | 說明全域資料庫 `global.db` 與各專案資料庫 `jobs.db` 的 Schema 定義。 |
| **📄 格式與接口** | 前端開發者 / 系統對接人員 | [📝 JSON 資料格式 (json_structure.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/json_structure.md) | 說明專案配置檔、座標範本（Safe Zone / Blocked Zones）等 JSON 資料欄位的規格。 |
| | 前端開發者 / API 對接人員 | [🌐 API 介面規格 (api.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/api.md) | 列出後端實際對外提供的所有 REST API 端點與 WebSocket 即時狀態推送協定。 |
| **💻 開發與測試** | 後端開發者 / 測試工程師 | [🛠️ 開發者指南 (developer_guide.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/developer_guide.md) | 後端 Singleton Core 引擎運作機制、環境設定與常見問題。 |
| | 後端開發者 / 測試工程師 | [🧪 測試指南 (testing_v2.md)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/testing_v2.md) | V2 測試策略、如何運行 Pytest 測試套件、以及新增測試的規範。 |

---

## 📂 封存歷史資料 (Archive)
為了保持主要文件區的整潔，歷史性或盤點性的靜態資料已被移至歸檔資料夾：
- [📦 專案盤點存檔 (archive/project_inventory_2026-03-15/)](file:///c:/Users/tange/Desktop/all_project/py for NKNU GA/AI_AGENT_LAB/docs/archive/project_inventory_2026-03-15/)：2026-03-15 專案初期的符號與程式碼歷史盤點檔案。

---

## ✍️ 文件撰寫與更新規範

當您新增或重構專案功能時，請務必遵循以下文件維護職責：
1. **修改後端 Router 端點時**：必須同步更新 `docs/api.md`。
2. **修改資料庫模型 (SQLAlchemy Models) 時**：必須產生 Alembic 遷移，並同步更新 `docs/database.md`。
3. **新增第三方依賴或變更啟動流程時**：必須更新 `docs/quickstart.md`。
4. **修改憑證範本產生邏輯時**：必須更新 `docs/json_structure.md` 與 `docs/backend_architecture.md`。
