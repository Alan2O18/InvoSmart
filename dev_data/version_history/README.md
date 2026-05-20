# 版本紀錄索引

本資料夾整理 Voucher Editor 與相關文件系統的版本里程碑。

- `v0_0_0.md`: 初始基線，尚未建立 Voucher Editor 正式流程
- `v0_0_1.md`: Voucher Editor 可用性與 UI 大修
- `v0_0_2.md`: PDF 正確下載、文字寫入確認與 Canvas 預覽
- `v0_0_3.md`: 文件系統對齊、API/docs 清理與版本整理
- `v0_0_4.md`: 錯誤修補造成的回歸版本，作為後續修復基線
- `v0_0_5.md`: 回補 V0.0.4 破壞後的穩定性修復
- `v0_0_6.md`: 憑證文字座標校準、預覽同步與 PDF 輸出收斂
- `v0_0_7.md`: 六格金額制度切換、防 silent truncation 與舊資料保護
- `v0_0_8.md`: 後端系統測試覆蓋率深度提升與防護網建立 (Coverage 77% → 84%)
- `v0_0_9.md`: 憑證編輯器 Bug 修補、字型溢位修正與視覺化設定頁面
- `v0_0_10.md`: 全生命週期工作流架構升級（影像管線、非同步強化、資料品質防護），並完成 Windows JXL 啟用收尾（465 tests + JXL migration closeout）
- `v0_0_11.md`: Settings 前端修復、多組長與電子章管理上線；模型列表自動抓取。另記錄「圖片問題尚未完全修復」
- `v0_0_12.md`: JXL 編碼器切換（pyvips -> imagecodecs）與預覽 API 修復，解決 JXL 前端預覽斷鏈
- `v0_0_13.md`: JXL 全鏈路相容性收尾（Adapter 讀取端、FileOps/Voucher/Router 統一路徑、pytest 補強）
- `v0_0_14.md`: 儲存空間清理與手動二切上線（啟動清理、JXL 優化、detect/apply-resplit、前端 ResplitModal）
- `v0_0_15_stamp_management.md`: 印章管理與群組/組長流程整理
- `v0_0_16_refactoring_and_cleanup.md`: 重構與清理版本，收斂舊實作與雜訊
- `v0_0_17_architecture_and_cleanup.md`: 架構整理與廢棄流程清理
- `v0_0_18_fileops_db_refactoring.md`: FileOps 與資料庫重構
- `v0_0_19_resplit_ui.md`: 二切/重切 UI 與流程調整
- `v0_0_20.md`: 印章綁定與自動蓋章系統
- `v0_0_21.md`: 使用者體驗與路由架構重構
- `v0_0_22.md`: 系統修復與模板管理升級
- `v0_0_23.md`: 嚴重缺陷修復與驗證收尾
