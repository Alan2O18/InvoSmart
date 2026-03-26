# implementation_plan.md.resolved.* 歷史計畫索引

**日期**: 2026-03-04
**說明**: 這些檔案是從專案最初的架構設計一路演進到 Voucher Editor 的完整計畫歷程。每個 `.resolved.N` 都是一次 Gemini Agent 的實作計畫快照。以下按時序編號整理。

---

## 0️⃣ 早期系統架構規劃 (Pre-Voucher Editor)

| # | 檔案 | 主題 | 內容摘要 |
|:---|:---|:---|:---|
| 0 | `resolved.0` | 系統初始藍圖 | 最早的開發規格：SQLAlchemy Models (Activity/InvoiceFile/TaskStatus)、PyMuPDF 引擎、Unit Test 計畫 |
| 1 | `resolved.1` | 架構更新版 | 發現現有 Project/Job 模型可直接沿用，不需從頭建表 |
| 2 | `resolved.2` | 完整規格書 | 雙軌制 UI (總務核銷專區 + Kanban)、指令式混合處理工作流、搜尋型 PDF (隱形文字層) 黑科技 |
| 3 | `resolved.3` | 第一次架構審核 | 深度 Gap Analysis (G1-G7)、風險評估、ER Diagram 修正、分 Phase 1-4 執行藍圖 |
| 4 | `resolved.4` | 第二次架構審核 | 與 resolved.3 內容相近，加入 VLM-First V2 哲學、座標轉換矩陣 (Affine Transform)、Worker 並發管理 |
| 5 | `resolved.5` | 精簡版審核報告 | resolved.3/4 的精煉版本，7 項 Gap + 風險評估 + DB 擴充 + Phase 1-4 藍圖 |

---

## 1️⃣ PDF 處理系統建設 (PDF Engine + Worker)

| # | 檔案 | 主題 | 內容摘要 |
|:---|:---|:---|:---|
| 6-8 | `resolved.6-8` | PDF Engine 實作 | `pdf_engine.py` 純函式開發、PDF Worker Thread、API 整合 |
| 9 | `resolved.9` | 雙軌 PDF 重構 | **關鍵文件**：盤點所有涉及 PDF 的前後端檔案、分析 PdfWorkbench 白畫面 Root Cause (pdf.js Worker CDN 問題)、提出 Part 1 (憑證黏貼紙) + Part 2 (PDF 編輯器修復) 分離計畫 |

---

## 2️⃣ Voucher Editor 獨立頁面建設

| # | 檔案 | 主題 | 內容摘要 |
|:---|:---|:---|:---|
| 10 | `resolved.10` | 完全重做計畫 | **里程碑**：首次提出 `VoucherEditorView.vue` 獨立頁面、T0_voucher.pdf 範本分析 (座標表)、前後端解耦架構 (GET /preview + POST /generate)、Fabric.js overlay 拖拉編輯 |
| 11-15 | `resolved.11-15` | 迭代精修 | 座標校準、安全區 (535×336 pts)、API Schema 定義、Canvas 初始化邏輯 |
| 16-20 | `resolved.16-20` | 防禦清單建設 | 逐步建立會計防呆機制 (日期驗證、金額格式、發票去重、狀態同步) |
| 21-26 | `resolved.21-26` | UX 與算法 | 用途拼接邏輯、憑證號串號算法、自動縮字防截斷、碰撞偵測設計 |

---

## 3️⃣ 深度防禦系統 (Fix 系列)

| # | 檔案 | 主題 | 內容摘要 |
|:---|:---|:---|:---|
| 27 | `resolved.27` | v18 — Fix 32-36 | **Fix 32**: 台幣無條件進位 + 標黃 · **Fix 34**: 專案 ID 路徑穿越防禦 (Sanitization) · **Fix 35**: 空字串崩潰攔截 (PyMuPDF `insert_textbox` 零長度防護) · **Fix 36**: Canvas Viewport 絕對座標還原 (反向 viewportTransform 運算) |
| 28-30 | `resolved.28-30` | Fix 系列延續 | 更多邊界情況修復、非法日期鎖死閥、Retina 防模糊、浮點淨化 |
| 31-35 | `resolved.31-35` | 終極整合 | 46 項防禦清單最終定稿 (v27 究極計畫的前身)、Layout JSON Schema (Draft vs Strict 雙軌驗證)、VoucherLayoutPayload Pydantic Model |

---

## 📋 與當前 V32 計畫的關聯

從上述歷史計畫中，以下功能曾被詳細設計但**在實作過程中遺失或未被實現**：

| 歷史來源 | 功能 | V32 對應項 | 狀態 |
|:---|:---|:---|:---|
| resolved.27 Fix 32 | 台幣無條件進位 + 金額標黃 | V32 #1 欄位高光驗證 | 🟡 半成品 |
| resolved.27 Fix 35 | 空字串崩潰防護 | 已在 `voucher_generator.py` 實現 | ✅ 已實現 |
| resolved.27 Fix 34 | 路徑穿越 Sanitization | 已在 `voucher_layout_repo.py` 實現 | ✅ 已實現 |
| resolved.27 Fix 36 | Canvas Viewport 絕對座標還原 | 目前未使用 Zoom/Pan 故暫無問題 | ⚪ 暫不需要 |
| resolved.10 | Fabric.js 拖拉編輯 | 已實現 | ✅ 已實現 |
| resolved.9 | PdfWorkbench 白畫面修復 | 已將 PDF 編輯器功能分離出去 | ✅ 已繞過 |
| resolved.21-26 | 碰撞偵測、用途拼接、串號算法 | V32 #2 碰撞 / V32 #5 覆蓋保護 | 🔴 遺漏 |
| resolved.31-35 | 自動排版 O(N log H) | V32 #4 自動排版 | 🔴 遺漏 |
