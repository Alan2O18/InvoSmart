# Gemini 2.5 Flash Lite Thinking Implementation Plan

> **Status**: Planning
> **Date**: 2026-02-04
> **Goal**: Update `VisionHandler` to utilize the **Thinking** capability of `gemini-2.5-flash-lite` for better reasoning in receipt processing.

### Code Update

#### [MODIFY] [vision_handler.py](file:///c:/Users/tange/Desktop/all_project/py/for/NKNU/GA/AI_AGENT_LAB/backend/processing/vision_handler.py)
Update the `VisionHandler` class to use the new `google-genai` SDK.
- Switch from `google.generativeai` to `google.genai`.
- In `_init_client`: Use `genai.Client`.
- In `_call_with_retry`: 
    - Use `client.models.generate_content`.
    - Pass `config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(include_thoughts=True, include_thinking_tokens=True, thinking_budget=...))`
    - Update extraction logic to handle `response.candidates[0].content.parts`.

## Verification Plan

### Automated Tests
1. **Run `test_vision.py`**:
   - Command: `micromamba run -n OCR_GA python test_vision.py`
   - Expectation: 
     - Successful identification of the receipt.
     - Logs showing the "Thinking" process via the new SDK's response structure.

### Manual Verification
- Verify that the output quality improves or remains high with thinking enabled.
- Ensure no API errors occur with the new model name.
