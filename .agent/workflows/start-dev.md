---
description: How to start the full AI Agent Lab application (Backend + Frontend)
---

# Start Development Environment (Full App)

This workflow guides you through starting both the unified FastAPI backend (VLM-First V2) and the Vue 3 frontend. 
Because running both requires two separate long-running processes, you will need to open two separate terminal windows.

## Prerequisites
1. **Backend**: Ensure the `OCR_GA` Python environment is configured and your `GOOGLE_API_KEY` is set in `.env`. (Note: use `uv pip install` for any new Python packages).
2. **Frontend**: Ensure Node.js is installed and `npm install` has been run in the `frontend/` directory.

---

## Terminal 1: Start the Backend

Open your first terminal and run:

// turbo-all
```bash
micromamba activate OCR_GA
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
*The API will be available at http://localhost:8000/docs*

---

## Terminal 2: Start the Frontend

Open a **new, separate terminal tab/window** and run:

// turbo-all
```bash
cd frontend
npm run dev
```
*The Web UI will be available at http://localhost:5173*
