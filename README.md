# AI Agent Lab - OCR & LLM Pipeline

This project is a full-stack application designed to process invoice images using OCR (Optical Character Recognition) and LLM (Large Language Model) technologies. It provides a user-friendly interface for managing projects, splitting invoice images, extracting text, and structuring data.

## Technology Stack

### Frontend
*   **Framework**: Vue.js 3
*   **Build Tool**: Vite
*   **HTTP Client**: Axios
*   **Routing**: Vue Router
*   **Styling**: CSS (Dark Theme)

### Backend
*   **Framework**: FastAPI (Python)
*   **OCR Engine**: PaddleOCR
*   **Image Processing**: OpenCV, NumPy
*   **Database**: SQLite (per project)
*   **Task Management**: Thread-based worker queues (CPU for OCR, GPU for LLM)

## Project Structure

```
AI_AGENT_LAB/
├── backend/
│   ├── routers/            # API endpoints (projects.py, websocket.py)
│   ├── services/           # Core logic (engine.py)
│   ├── processing/         # OCR and LLM handlers
│   ├── utils/              # Utility functions
│   ├── main.py             # Application entry point
│   └── ...
├── frontend/
│   ├── src/
│   │   ├── views/          # Vue components (pages)
│   │   ├── services/       # API integration
│   │   └── ...
│   └── ...
├── README.md               # This file
└── ...
```

## Setup & Running

### Prerequisites
*   Python 3.8+
*   Node.js 16+
*   PaddleOCR dependencies

### Backend
1.  Navigate to the root directory.
2.  Install Python dependencies (if not already installed).
3.  Run the server:
    ```bash
    uvicorn backend.main:app --reload
    ```
    The backend runs on `http://localhost:8000`.

### Frontend
1.  Navigate to the `frontend` directory.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Run the development server:
    ```bash
    npm run dev
    ```
    The frontend runs on `http://localhost:5173`.

## Key Features

1.  **Project Management**: Create, view, and manage invoice processing projects.
2.  **Image Splitting**: Automatically split scanned invoice pages into individual invoice images.
3.  **OCR Processing**: Extract text from images using PaddleOCR.
4.  **LLM Structuring**: Convert OCR text into structured JSON data using an LLM.
5.  **Export**: Export processed data to Excel.
6.  **Raw File Management**: View, split, and delete raw uploaded files.
7.  **Job Management**: Monitor status, rotate images, and delete individual jobs.

## API Endpoints

### Projects
*   `GET /api/projects`: List all projects.
*   `POST /api/projects`: Create a new project.
*   `GET /api/projects/{id}`: Get project status.
*   `PUT /api/projects/{id}`: Update project metadata.
*   `DELETE /api/projects/{id}`: Delete a project.
*   `POST /api/projects/{id}/activity_info`: Update activity-specific metadata.

### Files & Processing
*   `POST /api/projects/{id}/add_files`: Upload raw or split files.
*   `GET /api/projects/{id}/raw_files`: List raw files.
*   `DELETE /api/projects/{id}/raw_files/{filename}`: Delete a raw file.
*   `POST /api/projects/{id}/rotate/{filename}`: Rotate an image.
*   `POST /api/projects/{id}/run_split`: Start splitting process for all raw files.
*   `POST /api/projects/{id}/split/{filename}`: Split a specific raw file.
*   `POST /api/projects/{id}/run_ocr`: Start OCR processing for all jobs.
*   `POST /api/projects/{id}/run_llm`: Start LLM processing for all jobs.

### Jobs
*   `GET /api/projects/{id}/jobs`: List all jobs.
*   `DELETE /api/projects/{id}/jobs/{job_id}`: Delete a specific job.
*   `POST /api/projects/{id}/jobs/{job_id}/ocr`: Run OCR for a single job.
*   `POST /api/projects/{id}/jobs/{job_id}/llm`: Run LLM for a single job.

### Export & Archive
*   `POST /api/projects/{id}/run_export`: Export project data to Excel.
*   `POST /api/projects/{id}/run_archive`: Archive project (zip/7z).
*   `POST /api/projects/{id}/regenerate`: Regenerate project from an Excel archive.

### Groups
*   `GET /api/groups`: List all groups.
*   `POST /api/groups`: Create or update a group.
*   `DELETE /api/groups/{group_name}`: Delete a group.

## Troubleshooting

*   **Upload Errors**: Check the backend console logs for detailed error messages.
*   **Image Previews**: Ensure the backend server is running to serve static files.

## Comprehensive Test Suite

The project includes a comprehensive test suite covering all Engine functions, API endpoints, and integration use cases.

### Engine Functions Tested
| Function | Category | Test Type |
|----------|----------|-----------|
| `create_project` | Project | Unit |
| `get_task_manager` | Core | Unit |
| `run_splitting` | FileOps | Unit |
| `get_raw_files` | FileOps | Unit |
| `add_project_files` | FileOps | Unit |
| `rotate_image` | FileOps | Unit |
| `delete_raw_file` | FileOps | Unit |
| `run_ocr` | Processing | Unit |
| `run_llm` | Processing | Unit |
| `run_single_ocr` | Processing | Unit |
| `run_single_llm` | Processing | Unit |
| `delete_job` | Jobs | Unit |
| `run_excel` | Export | Unit |
| `archive_project` | Export | Unit |
| `regenerate_project` | Export | Unit |

### API Endpoints Tested
| Endpoint | Method | Test Type |
|----------|--------|-----------|
| `/` | GET | Unit |
| `/` | POST | Unit |
| `/{id}` | PUT | Unit |
| `/{id}` | DELETE | Unit |
| `/{id}/status` | GET | Unit |
| `/{id}/add_files` | POST | Unit |
| `/{id}/rotate/{filename}` | POST | Unit |
| `/{id}/run_split` | POST | Unit |
| `/{id}/split/{filename}` | POST | Unit |
| `/{id}/raw_files` | GET | Unit |
| `/{id}/run_ocr` | POST | Unit |
| `/{id}/run_llm` | POST | Unit |
| `/{id}/run_export` | POST | Unit |
| `/{id}/run_archive` | POST | Unit |
| `/{id}/jobs/{job_id}/ocr` | POST | Unit |
| `/{id}/jobs/{job_id}/llm` | POST | Unit |
| `/{id}/jobs/{job_id}` | DELETE | Unit |
| `/{id}/raw_files/{filename}` | DELETE | Unit |
| `/{id}/activity_info` | POST | Unit |
| `/{id}/regenerate` | POST | Unit |
| `/groups/list` | GET | Unit |
| `/groups` | POST | Unit |
| `/groups/{name}` | DELETE | Unit |
| `/{id}/jobs` | GET | Unit |

### Integration Use Cases
1. **Full Project Lifecycle**: Create → Upload → Split → OCR → LLM → Export → Archive
2. **Manual Correction Flow**: Create → Process → Export → Human Edit → Regenerate
3. **Partial Reprocessing**: Create → Split → Single OCR → Single LLM
4. **Group Management Flow**: Create Group → Assign to Project → List → Delete
5. **File Management Flow**: Add Raw → Get Raw → Rotate → Delete Raw

### How to Run Tests
```bash
# Run all tests
pytest

# Run by category
pytest -m engine      # Engine unit tests
pytest -m api         # API unit tests
pytest -m integration # Integration use cases
```
