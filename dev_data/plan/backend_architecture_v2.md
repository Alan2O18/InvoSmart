# 後端架構圖 (Backend Architecture) - VLM V2

> **狀態**: 已實作 (Implemented)
> **日期**: 2026-02-17
> **核心策略**: VLM-First (Vision Language Model 優先)，移除傳統 OCR 依賴。

---

## 1. 系統分層架構 (System Layering)

本系統採用四層架構，強調**關注點分離 (Separation of Concerns)** 與 **依賴注入 (Dependency Injection)**。

```mermaid
classDiagram
    direction TB
    
    class API_Layer {
        <<FastAPI Routers>>
        +projects.py (專案管理)
        +jobs.py (任務查詢)
        +config.py (系統設定)
        +suggestions.py (建議詞)
    }
    
    class Engine_Layer {
        <<Core Coordination>>
        +Engine (Singleton Facade)
        +GlobalWorker (背景任務)
        +FileOps (檔案操作)
        +ExportHandler (匯出邏輯)
    }
    
    class Repository_Layer {
        <<Data Access>>
        +ProjectRepository (Global DB)
        +JobRepository (Per-Project DB)
        +SuggestionRepository (Autocomplete)
    }
    
    class Processing_Layer {
        <<Business Logic>>
        +ReceiptProcessor (Main Pipeline)
    }
    
    class Handler_Layer {
        <<External Integration>>
        +VisionHandler (OpenAI/Gemini)
        +QRHandler (QReader/Local)
        +PythonValidator (Pure Logic)
    }
    
    API_Layer --> Engine_Layer : 1. 調用核心功能
    Engine_Layer --> Repository_Layer : 2. 存取資料
    Engine_Layer --> Processing_Layer : 3. 執行識別任務
    Processing_Layer --> Handler_Layer : 4. 調用底層能力
    
    note right of Engine_Layer
        Engine 負責協調 Workers 與 Repositories，
        不再包含業務邏輯。
    end note
```

---

## 2. 核心類別設計 (Core Class Design)

### Engine 與 Repository
`Engine` 作為系統的入口點，管理所有 Repositories 的生命週期。

```mermaid
classDiagram
    class Engine {
        -config: dict
        -project_repo: ProjectRepository
        -receipt_processor: ReceiptProcessor
        -task_queue: Queue
        +run_processing(project_id)
        +get_job_repo(project_id) JobRepository
    }
    
    class ProjectRepository {
        -global_db_path: Path
        +list_projects()
        +create_project()
        +update_project_status()
    }
    
    class JobRepository {
        -db_path: Path
        +list_jobs()
        +insert_job()
        +update_job()
        +complete_vlm()
    }

    class SuggestionRepository {
        -db_path: Path
        +search(category, query)
        +add_or_update(category, value)
    }
    
    Engine "1" *-- "1" ProjectRepository
    Engine "1" *-- "many" JobRepository : Cache per project
    Engine "1" *-- "1" ReceiptProcessor
```

### Processing Pipeline (VLM-First)
不再使用 RapidOCR 作為主要流程，而是作為 fallback 或被移除。目前流程完全依賴 VLM。

```mermaid
classDiagram
    class ReceiptProcessor {
        -vision_handler: VisionHandler
        -qr_handler: QRHandler
        -validator: PythonValidator
        +process(image_array) dict
    }
    
    class VisionHandler {
        <<OpenAI Compatible>>
        -client: OpenAI
        -model_name: "gemini-flash-lite"
        +process_image(image) tuple
    }
    
    class QRHandler {
        <<QReader>>
        +detect_and_decode(image) dict
    }
    
    class PythonValidator {
        <<Logic>>
        +validate(data) ValidationResult
    }
    
    ReceiptProcessor --> VisionHandler : 1. 用圖生文 (JSON)
    ReceiptProcessor --> QRHandler : 2. 提取 QR (驗證用)
    ReceiptProcessor --> PythonValidator : 3. 數學驗算
```

---

## 3. 資料流流程 (Data Flow)

**VLM-First Pipeline**:

```mermaid
sequenceDiagram
    participant Worker as GlobalWorker
    participant RP as ReceiptProcessor
    participant VLM as VisionHandler (Gemini)
    participant QR as QRHandler
    participant Val as Validator
    
    Worker->>RP: process(image)
    
    rect rgb(200, 220, 240)
        note right of RP: Step 1: VLM Analysis
        RP->>VLM: process_image(image)
        VLM-->>RP: {header, items, summary...} (JSON)
    end
    
    rect rgb(220, 240, 200)
        note right of RP: Step 2: QR Verification (Optional)
        RP->>QR: detect_and_decode(image)
        alt QR Found
            QR-->>RP: {invoice_id, date, total...}
            RP->>RP: merge_qr_data() (QR 高優先級)
        else No QR
            QR-->>RP: None
        end
    end
    
    rect rgb(240, 200, 200)
        note right of RP: Step 3: Logic Validation
        RP->>Val: validate(merged_data)
        Val-->>RP: {is_valid, confidence, issues}
    end
    
    RP-->>Worker: Final Result
```

---

## 4. PlantUML 原始碼 (Source)

```plantuml
@startuml
!theme plain
hide empty members
skinparam classAttributeIconSize 0

package "Engine Layer" {
    class Engine {
        - config: Dict
        - task_queue: Queue
        + run_processing(project_id)
        + get_job_repo(project_id): JobRepository
    }
    
    class GlobalWorker {
        + global_receipt_worker_loop()
    }
}

package "Repository Layer" {
    class ProjectRepository {
        <<Global DB>>
        + list_projects()
        + setup_project()
    }
    
    class JobRepository {
        <<Project DB>>
        + insert_job()
        + update_job()
    }
    
    class SuggestionRepository {
        <<Global DB>>
        + search()
        + upsert()
    }
}

package "Processing Layer" {
    class ReceiptProcessor {
        + process(image): Dict
        - _merge_qr_data()
    }
}

package "Handler Layer" {
    class VisionHandler {
        <<OpenAI SDK>>
        + process_image(image): Dict
    }
    
    class QRHandler {
        <<QReader>>
        + detect_and_decode(image): Dict
    }
    
    class PythonValidator {
        + validate(data): Result
    }
}

Engine --> ProjectRepository
Engine --> JobRepository : creates
Engine --> ReceiptProcessor
Engine --> GlobalWorker : starts

ReceiptProcessor --> VisionHandler
ReceiptProcessor --> QRHandler
ReceiptProcessor --> PythonValidator

@enduml
```
