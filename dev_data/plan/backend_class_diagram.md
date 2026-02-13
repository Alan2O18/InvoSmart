# 後端類別圖 (Backend Class Diagram) - VLM First Architecture

> **狀態**: 規劃中 (Simplified)
> **最後更新**: 2026-02-07
> **目標**: 極端簡化架構，移除本地 OCR 與分流邏輯，全面採用 VLM (Gemini Flash Lite)。

---

## 1. 系統分層架構 (Simplified)

```mermaid
classDiagram
    direction TB
    
    class API_Layer {
        <<FastAPI Routers>>
        +projects.py
        +jobs.py
    }
    
    class Engine_Layer {
        <<核心協調器>>
        +Engine
        +Workers
    }
    
    class Processing_Layer {
        <<處理邏輯>>
        +ReceiptProcessor
    }
    
    class Handler_Layer {
        <<專項處理器>>
        +VisionHandler
        +QRHandler
        +PythonValidator
    }
    
    API_Layer --> Engine_Layer : 調用
    Engine_Layer --> Processing_Layer : 觸發處理
    Processing_Layer --> Handler_Layer : 使用
```

---

## 2. Processing 模組 (核心處理)

```mermaid
classDiagram
    class ReceiptProcessor {
        -config: dict
        -vision_handler: VisionHandler
        -qr_handler: QRHandler
        -validator: PythonValidator
        +process(image_array) dict
        -_merge_qr_data(vlm_result, qr_data) dict
    }
    
    class VisionHandler {
        <<Gemini Flash Lite>>
        -api_key: str
        -model_name: str
        -client: Client
        +process_image(image) tuple~dict, dict~
    }
    
    class QRHandler {
        <<Local OpenCV>>
        +detect_and_decode(image) dict
    }
    
    class PythonValidator {
        <<Logic Check>>
        +validate(data) ValidationResult
    }
    
    ReceiptProcessor --> VisionHandler : 1. 主分析
    ReceiptProcessor --> QRHandler : 2. 輔助驗證
    ReceiptProcessor --> PythonValidator : 3. 邏輯檢查
```

---

## 3. 資料流方向 (Data Flow)

```mermaid
flowchart LR
    subgraph Input
        IMG[Image]
    end
    
    subgraph Processor
        RP[ReceiptProcessor]
    end
    
    subgraph External_AI
        VLM[Gemini Flash Lite]
    end
    
    subgraph Local_Utils
        QR[QR Code Scanner]
        Val[Python Validator]
    end
    
    subgraph Output
        JSON[Structured JSON]
    end
    
    IMG --> RP
    RP --> |1. 全圖上傳| VLM
    VLM --> |結構化資料| RP
    RP --> |2. 驗證電子發票| QR
    QR --> |QR 資料| RP
    RP --> |3. 合併與驗算| Val
    Val --> |最終結果| JSON
```

---

## 4. 介面契約 (Key Interfaces)

### ReceiptProcessor.process()
```python
def process(self, image_array: np.ndarray) -> dict:
    """
    單一入口，處理所有類型收據。
    
    不需指定模式，不需 OCR 前處理。
    直接將圖片送入 VLM，並嘗試掃描 QR Code 進行輔助驗證。
    
    Returns:
        {
            "success": bool,
            "result": {
                "header": {...},
                "items": [...],
                "summary": {...}
            },
            "metadata": {
                "vlm_model": "gemini-flash-lite",
                "qr_detected": bool,
                "confidence": float
            }
        }
    """
```

---

## 5. PlantUML Source

```plantuml
@startuml
!theme plain
hide empty members
skinparam classAttributeIconSize 0

package "Engine Layer" {
    class Engine {
        +run_processing(project_id)
    }

    class GlobalWorker <<Background Thread>> {
        +global_receipt_worker_loop(engine)
    }
}

package "Processing Layer" {
    class ReceiptProcessor {
        -vision_handler: VisionHandler
        -qr_handler: QRHandler
        -validator: PythonValidator
        +process(image_array): dict
        -_merge_qr_data(vlm_result, qr_data): dict
    }
}

package "Handler Layer" {
    class VisionHandler {
        <<Gemini Flash Lite>>
        -api_key: str
        -model_name: str
        +process_image(image): tuple<dict, dict>
    }

    class QRHandler {
        <<Local OpenCV>>
        +detect_and_decode(image): dict
    }

    class PythonValidator {
        +validate(data): ValidationResult
    }
}

Engine --> GlobalWorker
GlobalWorker --> ReceiptProcessor

ReceiptProcessor --> VisionHandler : 1. Analyze
ReceiptProcessor --> QRHandler : 2. Verify (Optional)
ReceiptProcessor --> PythonValidator : 3. Validate

@enduml
```
