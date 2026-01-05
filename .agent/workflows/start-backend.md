---
description: How to start the backend development server
---

# Backend Development Server

## Prerequisites
1. Ensure micromamba and OCR_GA environment are set up
2. Ensure Ollama is running with required models

## Start the Server

// turbo-all

1. Activate the OCR_GA environment:
```bash
micromamba activate OCR_GA
```

2. Pull required Ollama models (if not already done):
```bash
ollama pull qwen3-vl:2b
ollama pull qwen3:1.7b
```

3. Start the FastAPI backend server:
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Notes
- The server runs on port 8000 by default
- Use `--reload` for development (auto-restart on code changes)
- The unified ReceiptProcessor handles both OCR and LLM in a single pipeline
