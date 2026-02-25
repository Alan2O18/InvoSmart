---
description: How to start the backend FastAPI server (VLM-First V2)
---

# Backend Development Server

## Prerequisites
1. Ensure the `OCR_GA` environment is set up and activated.
2. Ensure your `GOOGLE_API_KEY` is set in `.env` or `config.json` (VLM-First architecture). No local Ollama is required.

## Start the Server

// turbo-all

1. Activate the OCR_GA environment:
```bash
micromamba activate OCR_GA
```

2. Start the FastAPI backend server:
```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## Notes
- The server API docs are available at http://localhost:8000/docs
- Use `--reload` for development (auto-restart on code changes)
- The system uses cloud VLM (Gemini/OpenRouter) for OCR and processing.
