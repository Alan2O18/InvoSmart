# backend/processing/prompts_config.py
"""
LLM Prompt 配置模組

所有 LLM prompts 使用 fstring 格式，支援：
- {ocr_text} - OCR 辨識原文
- {corrected_text} - 校正後文字
- {region} - 區域名稱
- {texts} - 文字列表
"""

# ==========================================
# OCR 文字校正 Prompt
# ==========================================

CORRECTION_PROMPT = """[INST]
You are a meticulous data correction robot. Your input is pre-formatted text from a Taiwanese e-invoice, which may contain OCR recognition errors.

**IMPORTANT: The input may be in Markdown format with structured elements like tables. Please preserve this formatting structure.**

**Primary Directive: ALL text in your output MUST be in Traditional Chinese (繁體中文). This is a non-negotiable rule.**

**Your Task:**
1.  **Semantic & OCR Error Correction**: Analyze the entire text for correctness. Your main goal is to fix OCR errors that arise from visual similarity or are contextually nonsensical.
    - **Example 1 (Visual Error)**: Correct `每報紙` to `海報紙`.
    - **Example 2 (Simplified Chinese)**: Convert `圆头笔` to `圓頭筆`.
    - **Example 3 (Common OCR Mistakes)**: Correct `电话` to `電話`.
2.  **Preserve Structure**: If the input contains Markdown tables or other structured formatting, maintain that structure in your output.
3.  **Output**: Return ONLY the full, corrected invoice text. If input is Markdown, output should also be Markdown with the same structure. Do NOT include any other explanations or surrounding text like "Here is the corrected text:".

<pre-formatted_invoice_text>
{ocr_text}
</pre-formatted_invoice_text>

Begin.
[/INST]"""


# ==========================================
# 結構化資料擷取 Prompt
# ==========================================

EXTRACTION_PROMPT = """[INST]
You are a data extraction robot.
Your input is a clean, corrected text from a Taiwanese e-invoice.

**IMPORTANT: The input may be in Markdown format with tables. Use the structured format to improve extraction accuracy.**

Your ONLY task is to extract the specified fields and return them in a single, valid JSON object.
Ensure all text in the output is in Traditional Chinese.

<invoice_text>
{corrected_text}
</invoice_text>

<json_output_format>
{{
    "supplier": "supplier_name",
    "invoice_id": "invoice_id",
    "date": "YYYY-MM-DD",
    "items": [
        {{"description": "product_name", "quantity": quantity, "price": price}}
    ],
    "total_amount": amount
}}
</json_output_format>
[/INST]"""


# ==========================================
# 收據 OCR 清洗 Prompt (整合自 receipt_llm_cleaner.py)
# ==========================================

CLEANING_PROMPT = """/no_think
你是收據資料清洗專家。請修正 OCR 錯誤並輸出 JSON。

OCR 結果:
買受人: {buyer}
日期: {date}
品項: {items}
合計: {total_chinese}
店章: {shop_name}

常見錯誤:
- 图→國, 大学→大學, 師大學→師範大學
- 壹干→壹仟, 贰→貳

直接輸出修正後的 JSON (不要解釋):
```json
{{
  "buyer": "修正後的買受人",
  "date": "日期 (YYYYMMDD)",
  "items": [{{"name": "品名", "total": 金額}}],
  "total_chinese": "修正後的大寫金額",
  "shop_name": "店名"
}}
```"""


# ==========================================
# 兩階段處理 - 語意分類 Prompt (整合自 receipt_twostep_llm.py)
# ==========================================

FIELD_TYPES = """
- BUYER: 買受人名稱 (公司、學校、機關)
- DATE: 日期 (民國年月日格式)
- ITEM_NAME: 品項名稱
- ITEM_QTY: 數量
- ITEM_PRICE: 單價
- ITEM_TOTAL: 小計金額
- TOTAL_NUM: 總金額數字
- TOTAL_CHINESE: 大寫金額 (壹貳參...)
- SHOP_NAME: 店家名稱
- SHOP_TEL: 店家電話
- TAX_ID: 統一編號 (8位數字)
- NOISE: 無意義文字 (表頭、格式字)
"""

CLASSIFICATION_PROMPT = """/no_think
你是收據 OCR 專家。判斷每個文字代表什麼欄位。

## 欄位類型
{field_types}

## OCR 文字 (區域: {region})
{texts}

## 任務
為每個文字標註類型，格式：
文字 → 類型

直接輸出結果："""


# ==========================================
# VLM 手寫收據提取 Prompt
# ==========================================

VLM_HANDWRITTEN_PROMPT = """/no_think
這是一張免用統一發票收據。請提取以下資訊並以 JSON 格式輸出：

必填欄位：
- buyer: 買受人（例：國立高雄師範大學）
- date: 日期（YYYYMMDD 格式）
- items: 品項列表 [{name, qty, price, total}]
- total: 合計金額（數字）
- total_chinese: 大寫金額
- shop_name: 店家名稱（從印章提取）
- tax_id: 統編（8位數字，如有）

直接輸出 JSON："""

# ==========================================
# 電子發票整合 Prompt (OCR + QR)
# ==========================================

ELECTRONIC_INVOICE_PROMPT = """[INST]
You are a smart invoice data merger.
I have two sources of information for the SAME electronic invoice:
1.  **QR Code Data**: Highly trusted for Invoice Number, Date, Total Amount, and Tax ID. (May lack item details)
2.  **OCR Text**: Contains the full text layout, including item names and quantities, but may have recognition errors.

**Your Task**:
Merge these two sources into a single, perfect JSON.
- **Trust QR Code** for: Invoice ID, Date, Seller Tax ID, Total Amount.
- **Trust OCR** for: Item details (Name, Quantity, Price).
- **Cross-check**: If OCR Total Amount mismatches QR Total Amount, trust QR.

<qr_data>
{qr_json}
</qr_data>

<ocr_text>
{ocr_text}
</ocr_text>

**Output Format**:
{{
    "receipt_type": "電子發票",
    "header": {{
        "supplier": "Extract from OCR (e.g. 7-ELEVEN)",
        "invoice_id": "From QR",
        "date": "From QR (YYYY-MM-DD)",
        "tax_id": "From QR"
    }},
    "items": [
        {{ "name": "Item Name from OCR", "qty": 1, "price": 100, "total": 100 }}
    ],
    "summary": {{
        "total": From QR
    }}
}}

Return ONLY the JSON.
[/INST]"""
