---
name: nknu-vlm-guard
description: Architecture guardrails for AI_AGENT_LAB backend layering and anti-bloat policy.
version: "0.0.16"
---

# NKNU VLM Guard

Use these rules before modifying backend architecture.

1. Router Layer (`backend/routers/*`)
- Only handle HTTP request/response, validation, and error mapping.
- Do not keep business logic blocks longer than 20 lines.
- Do not import `cv2` or `numpy` directly.
- Do not call `db.add()` or `db.execute()` directly; delegate to repository/service.

2. Service / Engine Layer (`backend/engine/*`)
- Orchestrate workflow across repositories and processors.
- Target class size <= 500 lines.
- Transitional exception: `FileOps` may stay around 550 lines in v0.0.16 and must be split in v0.0.17.

3. Processing Layer (`backend/processing/*`)
- Pure image/AI/text processing only.
- Stateless and no DB session ownership.
- Input: numpy array; output: numpy array or structured payload.
- No filesystem writes.

4. Repository Layer (`backend/repositories/*`)
- DB CRUD only.
- No business workflow, image processing, or filesystem I/O.
- Prefer DTO output to keep ORM/session boundaries stable.

5. Global Rules
- No single file beyond 800 lines.
- New feature/refactor must include at least one related unit test.
- Async routes must avoid synchronous filesystem/CPU blocking on event loop.
