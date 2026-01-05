# 快速開始指南 (Quickstart)

本指南說明如何設置開發環境並運行 Backend 服務。

## 環境需求

- **Python**: 3.10+
- **虛擬環境**: micromamba (推薦) 或 conda
- **Ollama**: 本地 LLM 服務
- **SQLite**: 內建資料庫

---

## 1. 啟用虛擬環境

```bash
# 使用 micromamba 啟用 OCR_GA 虛擬環境
micromamba activate OCR_GA

# 確認 Python 版本
python --version
# 預期輸出: Python 3.10.x 或以上
```

---

## 2. 安裝依賴

```bash
# 安裝 Python 依賴
pip install -r requirements.txt

# 主要依賴包括:
# - fastapi, uvicorn (Web 框架)
# - paddleocr, rapidocr-onnxruntime (OCR 引擎)
# - ollama (LLM 客戶端)
# - opencv-python, numpy (影像處理)
# - pandas, openpyxl (Excel 匯出)
```

---

## 3. 啟動 Ollama 服務

Backend 依賴本地 Ollama 服務進行 LLM 處理：

```bash
# 確認 Ollama 已安裝並運行
ollama list

# 如果未安裝，請前往 https://ollama.com 下載

# 下載所需模型
ollama pull qwen3:1.7b     # 文字校正和結構化
ollama pull qwen3-vl:2b    # 視覺識別 (VLM)
ollama pull gemma3:4b      # 修正器 (可選)
```

---

## 4. 啟動 Backend 服務

```bash
# 進入專案目錄
cd "c:\Users\tange\OneDrive\Desktop\all project\py for NKNU GA\AI_AGENT_LAB"

# 啟動開發伺服器
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 或使用快捷命令
python -m backend.main
```

服務啟動後可訪問：
- **API 文檔**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## 5. 驗證服務

```bash
# 檢查健康狀態
curl http://localhost:8000/api/health

# 列出專案
curl http://localhost:8000/api/projects

# 預期回應: {"status": "ok"} 或 []
```

---

## 6. 執行測試

```bash
# 啟用虛擬環境後執行測試
micromamba activate OCR_GA
pytest tests/ -v

# 執行測試並生成覆蓋率報告
pytest --cov=backend

# 僅執行特定測試
pytest tests/test_processing.py -v
pytest tests/test_utils.py -v
```

---

## 常見問題

### Q: `ModuleNotFoundError: No module named 'backend'`

**解決方案**: 確保從專案根目錄執行命令，並設置 PYTHONPATH：

```bash
# Windows
set PYTHONPATH=.

# Linux/Mac
export PYTHONPATH=.
```

### Q: `ollama.ResponseError: model not found`

**解決方案**: 下載所需模型：

```bash
ollama pull qwen3:1.7b
ollama pull qwen3-vl:2b
```

### Q: `ImportError: PaddleOCR not found`

**解決方案**: 安裝 PaddleOCR 或使用 RapidOCR：

```bash
pip install paddleocr
# 或使用輕量替代
pip install rapidocr-onnxruntime
```

---

## 下一步

- 查看 [API 參考文檔](./api_reference.md) 了解完整 API
- 查看 [架構說明](../backend/README.md) 了解模組設計
- 查看 [JSON Schema](./json_schema.md) 了解資料格式
