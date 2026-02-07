# 收據處理架構與流程規劃

> **狀態**: 草稿 / 規劃中
> **最後更新**: 2026-02-03
> **依據**: 使用者需求 & `docs/processing_pipeline.md`

## 1. 系統總覽 (System Overview)

本系統將上傳的收據影像（多為包含多張收據的A4掃描檔）處理為結構化資料 (JSON) 並匯出成 Excel。核心引擎管理著 分割 -> OCR -> 分流 -> 處理 -> 儲存 的流水線。

### 資料流向圖 (Data Flow Diagram)

```mermaid
graph TD
    Input[發票進來 Input] --> Split[切成單張 Split]
    Split --> OCR[OCR 識別]
    OCR --> Branch{分流 Branching}
    
    %% Branch 1: Electronic
    Branch -- 電子發票 --> Elec[電子式發票流程]
    Elec --> E_QR[掃 QR Code 拿資料]
    E_QR --> E_LLM[LLM 從 OCR 結果提資料]
    E_LLM --> E_Merge[對比合併 Merge]
    E_Merge --> DB_Save
    
    %% Branch 2: Handwritten
    Branch -- 手寫收據 --> Hand[手寫收據流程]
    Hand --> H_VLM[VisionHandler 提資料 (Visual Language Model)]
    H_VLM --> H_LLM[LLM 從 OCR 資料猜正不正確]
    H_LLM --> H_Merge[合併 Merge]
    H_Merge --> DB_Save
    
    %% Branch 3: Others
    Branch -- 其他影印收據 --> Other[其他收據流程]
    Other --> O_LLM[LLM 從 OCR 結果提資料]
    O_LLM --> DB_Save
    
    %% Storage & Export
    DB_Save[存入 DB] --> Export[匯出成 Excel]
```

---

## 2. 詳細處理流程 (Detailed Processing Flows)

每一步驟都對應特定的處理模組。

### 第一階段：前處理 (Phase 1: Pre-processing)

| 邏輯步驟 | 負責模組 / 類別 | 說明 |
| :--- | :--- | :--- |
| **輸入 (Input)** | `backend.managers.project_manager.ProjectManager` | 處理檔案上傳與專案建立。 |
| **分割 (Split)** | `backend.processing.receipt_splitter.ReceiptSplitter` |偵測 A4 上的收據輪廓並裁剪成單張影像。 |
| **OCR 識別** | `backend.processing.rapidocr_handler.RapidOCRHandler` | 對裁剪後的影像執行 OCR，獲取原始文字與座標 (Bounding Boxes)。 |

### 第二階段：分流與特定處理 (Phase 2: Branching & Specific Processing)

分流邏輯由 `backend.processing.receipt_processor.ReceiptProcessor` 管理。

#### A. 電子式發票 (Electronic Invoice)
*目標：標準台灣電子發票 (含 QR Code)。*

1.  **掃 QR Code 拿資料**
    *   **模組**: `backend.processing.qrcode_handler` (或 `ReceiptProcessor` 內部方法)
    *   **動作**: 解碼 QR Code 以獲取結構化資料（日期、金額、發票號碼）。
2.  **LLM 從 OCR 結果提資料**
    *   **模組**: `backend.processing.llm_handler.LLMHandler`
    *   **動作**: 使用 OCR 文字提取 QR Code 可能缺失的細節（例如 QR 內無詳細品項時）。
3.  **對比合併 (Merge & Validate)**
    *   **模組**: `backend.processing.receipt_processor.ReceiptProcessor` (邏輯層)
    *   **動作**: 比對 QR 資料與 LLM 提取資料。金額/日期以 QR 為準；LLM 負責填補缺漏。

#### B. 手寫收據 (Handwritten Receipt)
*目標：免用統一發票收據 (各類手寫格式)。*

1.  **VisionHandler 提資料 (Vision Extraction)**
    *   **模組**: `backend.processing.vision_handler.VisionHandler` (**新功能**)
    *   **動作**: 使用視覺語言模型 (Visual Language Model, 如 Qwen-VL) 直接「看」影像並提取欄位（手寫字對傳統 OCR 較困難）。
2.  **LLM 從 OCR 資料猜正不正確 (LLM Verification)**
    *   **模組**: `backend.processing.llm_handler.LLMHandler`
    *   **動作**: 將 VLM 的輸出與傳統 OCR 的輸出進行比對。利用 OCR 的文字結果來「或是」或「修正」VLM 的幻覺，或確認模糊的手寫字跡。
3.  **合併 (Merge)**
    *   **模組**: `backend.processing.receipt_processor.ReceiptProcessor`
    *   **動作**: 結合兩者的信心分數產出最終 JSON。

#### C. 其他影印收據 (Other Printed Receipts)
*目標：傳統長條發票、信用卡簽單、或其他印刷證明。*

1.  **LLM 從 OCR 結果提資料**
    *   **模組**: `backend.processing.llm_handler.LLMHandler`
    *   **動作**: 標準的 RAG/Extraction 流程，使用 OCR 文字填入 JSON Schema。

### 第三階段：收尾 (Phase 3: Post-processing)

| 邏輯步驟 | 負責模組 / 類別 | 說明 |
| :--- | :--- | :--- |
| **存入 DB** | `backend.database.DBManager` (及 `ProjectManager`) | 將結構化 JSON 與處理狀態存入資料庫。 |
| **匯出成 Excel** | `backend.engine.export.ExportHandler` | 從資料庫產生最終的 Excel 報表。 |

---

## 3. Engine 管理流程 (Engine Management Flow)

`backend.engine` 套件負責非同步地協調整個流程。

```mermaid
sequenceDiagram
    participant API as API / User
    participant Eng as Engine (Core)
    participant Q as Task Queue (任務佇列)
    participant W as Global Worker (統一 Worker)
    participant Proc as Receipt Processor

    API->>Eng: create_project(files) <br/> 建立專案
    Eng->>Eng: run_splitting(files) <br/> 執行分割
    
    par 非同步處理 (Async Processing)
        API->>Eng: run_processing(project_id)
        Eng->>Q: Put Job (Stage: OCR) <br/> 加入佇列
        
        loop Worker Loop (工作迴圈)
            W->>Q: Get Job <br/> 取出任務
            W->>Proc: process_receipt(image, mode="auto")
            
            activate Proc
            Proc->>Proc: 1. OCR (RapidOCR)
            Proc->>Proc: 2. Classify (分類: 電子/手寫/其他)
            
            alt Electronic (電子發票)
                Proc->>Proc: QR Scan + LLM Extract + Merge
            else Handwritten (手寫收據)
                Proc->>Proc: VLM Extract + LLM Verify
            else Other (其他)
                Proc->>Proc: LLM Extract
            end
            
            Proc-->>W: Result JSON
            deactivate Proc
            
            W->>Eng: Save Result to DB <br/> 存檔
            W->>Eng: Update Task Status <br/> 更新狀態
        end
    end
    
    API->>Eng: run_excel(project_id) <br/> 匯出報表
    Eng->>Eng: ExportHandler.generate()
```

### Engine 關鍵組件

*   **`backend.engine.core.Engine`**: 中央控制器。負責初始化管理器與佇列。
*   **`backend.engine.workers.GlobalReceiptWorker`**: 持續運行的迴圈，從 `task_queue` 消化任務。
*   **`backend.engine.core.Engine.task_queue`**: 儲存等待處理的 Job ID。
*   **`backend.managers.task_manager.TaskManager`**: 管理個別 Job 的狀態 (Pending -> Running -> Completed)。

---

## 4. 下一步 (Next Steps)

*   [ ] 實作 `VisionHandler` 以支援手寫收據處理。
*   [ ] 驗證 `ReceiptProcessor` 中的分流邏輯。
*   [ ] 確保 `ExportHandler` 支援合併後的資料結構。

---

## 5. 後端檔案盤點 (Backend File Audit)

以下列出 `backend` 主要目錄下的檔案及其功能與引用狀態。

### `backend/managers`
| 檔案 | 說明 | 狀態 (引用/被引用) |
| :--- | :--- | :--- |
| `job_repository.py` | 負責 Job 資料的持久化存取。 | ✅ 被 `TaskManager` 引用 |
| `job_state_machine.py` | 管理 Job 的狀態流轉 (Pending -> Running -> ...)。 | ✅ 被 `TaskManager` 引用 |
| `project_crud.py` | 專案層級的 CRUD 操作。 | ✅ 被 `ProjectManager` 引用 |
| `project_manager.py` | 專案管理的主要入口，整合 CRUD 與 Setup。 | ✅ **核心組件**，被 Engine 引用 |
| `project_setup.py` | 專案初始化邏輯 (建立目錄、設定檔)。 | ✅ 被 `ProjectManager` 引用 |
| `suggestion_repository.py` | 管理自動完成建議 (店家名、品項等)。 | ❓ 需確認是否整合至 API |
| `task_manager.py` | 任務管理的 Facade，包裝 Repository 與 StateMachine。 | ✅ **核心組件**，被 Engine 引用 |

### `backend/engine`
| 檔案 | 說明 | 狀態 (引用/被引用) |
| :--- | :--- | :--- |
| `archive_handler.py` | 負責專案的封存與壓縮。 | ✅ 被 `ExportHandler` 引用 |
| `core.py` | **Engine (核心)**。系統的中央控制器。 | ✅ **核心入口** |
| `excel_exporter.py` | 執行 Excel 報表生成的實際邏輯。 | ✅ 被 `ExportHandler` 引用 |
| `export.py` | 匯出功能的 Facade (整合 Excel 與 Archive)。 | ✅ 被 Engine 引用 |
| `file_ops.py` | 處理檔案操作 (旋轉、刪除、列表)。 | ✅ 被 Engine 引用 |
| `regeneration_handler.py` | 從封存檔還原專案的邏輯。 | ✅ 被 `ExportHandler` 引用 |
| `workers.py` | 背景工作 (Background Workers) 的執行迴圈。 | ✅ 被 Engine 啟動 |

### `backend/processing`
| 檔案 | 說明 | 狀態 (引用/被引用) |
| :--- | :--- | :--- |
| `audit_handler.py` | 負責資料稽核或記錄變更 (?)。 | ❓ 需確認用途 |
| `contour_validator.py` | 驗證切割出的輪廓是否為有效收據。 | ✅ 被 `ReceiptSplitter` 引用 |
| `hough_corner_detector.py` | 基於 Hough Transform 的角點偵測 (用於切割)。 | ✅ 被 `ReceiptSplitter` 引用 |
| `image_preprocessor.py` | 影像前處理 (二值化、降噪等)。 | ✅ 被 `ReceiptSplitter` / OCR 引用 |
| `keyword_classifier.py` | 基於關鍵字對收據進行分類 (電子/手寫/其他)。 | ✅ 被 `ReceiptProcessor` 引用 |
| `llm_handler.py` | 封裝與 LLM (Local/Cloud) 的互動邏輯。 | ✅ 被 `ReceiptProcessor` 引用 |
| `perspective_transform.py` | 執行透視變換 (校正歪斜影像)。 | ✅ 被 `ReceiptSplitter` 引用 |
| `prompts_config.py` | 集中管理 LLM 的 Prompt Template。 | ✅ 被 `LLMHandler` 引用 |
| `python_validator.py` | 驗證或執行 Python 程式碼 (可能用於沙箱環境)。 | ❓ 需確認用途 |
| `qr_handler.py` | QR Code 掃描與解析。 | ✅ 被 `ReceiptProcessor` 引用 |
| `rapidocr_handler.py` | 封裝 RapidOCR 引擎。 | ✅ 被 `ReceiptProcessor` 引用 |
| `receipt_processor.py` | **處理核心**。管理 OCR/LLM/分流邏輯。 | ✅ 被 global worker 引用 |
| `receipt_splitter.py` | 負責將 A4 掃描檔切割為單張收據。 | ✅ 被 Engine 引用 |
| `receipt_virtual_ocr.py` | (舊版) 虛擬區域 OCR 邏輯。 | ❌ **已刪除 (Deleted)** |
| `vision_handler.py` | **VisionHandler** (VLM)。處理手寫收據。 | ✅ 被 `ReceiptProcessor` 引用 (規劃中) |

---

## 6. 程式碼追蹤流程圖 (Code-Traced Flow Diagrams)

以下流程圖基於 **實際程式碼** 追蹤繪製，反映目前的實作狀態。

### 6.1 Worker 主迴圈 (`global_receipt_worker_loop`)

```mermaid
flowchart TD
    subgraph Worker ["global_receipt_worker_loop (workers.py)"]
        Start([Worker 啟動]) --> WaitTask[從 task_queue.get 取得任務]
        WaitTask --> ParseTask{解析任務}
        ParseTask --> |"(project_id, job_id, stage_limit)"| GetTM[取得 TaskManager]
        GetTM --> CheckJob{檢查 Job 狀態}
        CheckJob --> |不存在或非 pending| Skip[跳過]
        CheckJob --> |pending/ready| MarkRunning[標記為 running]
        MarkRunning --> ReadImage[讀取圖片 cv_imread_chinese]
        ReadImage --> CheckStage{stage_limit?}
        
        CheckStage --> |"ocr"| OCR_Stage
        CheckStage --> |"llm"| LLM_Stage
        CheckStage --> |None| SkipNoStage[跳過 - 未指定階段]
        
        subgraph OCR_Stage ["OCR 階段"]
            OCR1[process_ocr_only] --> OCR2[complete_ocr]
        end
        
        subgraph LLM_Stage ["LLM 階段"]
            LLM1[get_job_details 取 OCR 結果] --> LLM2{OCR 結果有效?}
            LLM2 --> |否| FailJob[fail_job]
            LLM2 --> |是| LLM3[process_llm_only]
            LLM3 --> LLM4[complete_llm]
        end
        
        OCR_Stage --> Done[task_done]
        LLM_Stage --> Done
        Skip --> Done
        SkipNoStage --> Done
        Done --> WaitTask
    end
```

### 6.2 OCR 階段處理 (`process_ocr_only`)

```mermaid
flowchart TD
    subgraph OCR ["ReceiptProcessor.process_ocr_only"]
        Input[image_array] --> Step1["Step 1: OCR<br/>ocr_handler.do_ocr()"]
        Step1 --> Step2["Step 2: 關鍵字分類<br/>qr_handler.detect_and_decode()<br/>classifier.classify()"]
        Step2 --> Step3["Step 3: 簡單排版<br/>to_plain_text()"]
        
        Step3 --> BuildResult["組裝 ocr_result<br/>{text, type}"]
        BuildResult --> Return["返回<br/>{success, invoice_type, ocr_result, ocr_stats}"]
    end
```

### 6.3 LLM 階段處理 (`process_llm_only`)

```mermaid
flowchart TD
    subgraph LLM ["ReceiptProcessor.process_llm_only"]
        Input["ocr_result: {text, type}<br/>image_array (optional)"] --> Parse["解析 receipt_type_str"]
        Parse --> Branch{分流判斷}
        
        Branch --> |"電子" in type| Elec["_process_electronic()"]
        Branch --> |"手寫/免用" in type| Hand["_process_handwritten()"]
        Branch --> |其他| Other["_process_other()"]
        
        subgraph Electronic ["_process_electronic"]
            E1["qr_handler.detect_and_decode()"] --> E2{QR 有效?}
            E2 --> |否| E_Fallback["降級為 _process_other()"]
            E2 --> |是| E3["llm_handler.call_with_thinking()<br/>(ELECTRONIC_INVOICE_PROMPT)"]
            E3 --> E4["_parse_json_from_text()"]
        end
        
        subgraph Handwritten ["_process_handwritten"]
            H1["檢索詞庫 _retrieve_vocabulary()"] --> H2["vision_handler.process_handwritten()<br/>(image, prompt_context)"]
            H2 --> H3["_parse_json_from_text()"]
        end
        
        subgraph OtherFlow ["_process_other"]
            O1["llm_handler.call_with_thinking()<br/>(內嵌 Prompt)"] --> O2["_parse_json_from_text()"]
        end
        
        Elec --> Validate
        Hand --> Validate
        Other --> Validate
        
        Validate["Step 3: 驗算<br/>validator.validate()"] --> Assemble["Step 4: 組裝結果"]
        Assemble --> Return["返回<br/>{success, llm_result, llm_stats, confidence}"]
    end
```

### 6.4 模組呼叫關係圖 (Module Call Graph)

```mermaid
graph LR
    subgraph Engine
        Core[core.py] --> FileOps[file_ops.py]
        Core --> Export[export.py]
        Core --> Workers[workers.py]
    end
    
    subgraph Processing
        Workers --> RP[receipt_processor.py]
        RP --> OCR[rapidocr_handler.py]
        RP --> KC[keyword_classifier.py]
        RP --> QR[qr_handler.py]
        RP --> VH[vision_handler.py]
        RP --> LLM[llm_handler.py]
        RP --> PV[python_validator.py]
        LLM --> PC[prompts_config.py]
    end
    
    subgraph Splitting
        FileOps --> RS[receipt_splitter.py]
        RS --> HCD[hough_corner_detector.py]
        RS --> PT[perspective_transform.py]
        RS --> CV[contour_validator.py]
        RS --> IP[image_preprocessor.py]
    end
    
    subgraph Managers
        Core --> PM[project_manager.py]
        Core --> TM[task_manager.py]
        TM --> JR[job_repository.py]
        TM --> JSM[job_state_machine.py]
        PM --> PCRUD[project_crud.py]
        PM --> PS[project_setup.py]
    end
```

### 6.5 資料流詳細圖 (Detailed Data Flow)

```mermaid
flowchart LR
    subgraph Input
        A4[A4 掃描檔]
    end
    
    subgraph Split
        A4 --> RS[ReceiptSplitter]
        RS --> |"單張影像 []"| Jobs[(jobs.db)]
    end
    
    subgraph OCR_Phase ["OCR 階段"]
        Jobs --> Worker1[Worker stage=ocr]
        Worker1 --> OCR_Proc[process_ocr_only]
        OCR_Proc --> |"ocr_result: {text, type}"| Jobs
    end
    
    subgraph LLM_Phase ["LLM 階段"]
        Jobs --> Worker2[Worker stage=llm]
        Worker2 --> LLM_Proc[process_llm_only]
        
        LLM_Proc --> |電子| Elec_Flow["QR + LLM"]
        LLM_Proc --> |手寫| Hand_Flow["VisionHandler"]
        LLM_Proc --> |其他| Other_Flow["LLM"]
        
        Elec_Flow --> |JSON| Jobs
        Hand_Flow --> |JSON| Jobs
        Other_Flow --> |JSON| Jobs
    end
    
    subgraph Export
        Jobs --> Excel[ExportHandler]
        Excel --> XLSX[Excel 報表]
    end
```

---

> **備註**: 上述流程圖基於 2026-02-04 的程式碼追蹤。若程式碼有更新，請同步更新此文件。


