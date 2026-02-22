import os
import json
import requests
import sys

def main():
    # 讀取 config.json 來找 API key
    config_path = "config.json"
    api_key = None
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
            api_key = config.get("vlm_settings", {}).get("api_key")
            model = config.get("vlm_settings", {}).get("model", "gemini-2.5-flash")

    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
        
    if not api_key:
        print("Error: 無法在 config.json 或環境變數 GEMINI_API_KEY 找到 API 金鑰。")
        sys.exit(1)

    # Note: gemini-2.5-flash-lite might not support outputting thoughts directly even with native API.
    # We will test gemini-2.5-pro or gemini-2.5-flash which definitively support it.
    model = "gemini-2.5-pro"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    headers = {
        "Content-Type": "application/json"
    }

    # Prompt user to input something to think about, or use a default
    prompt = "請詳細解釋為什麼天空是藍色的？請盡量用通俗易懂的方式，並在回答前仔細思考物理原理。"

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }],
        "generationConfig": {
            # Let's see if we can force thinking to be included in the response
            "thinkingConfig": {
                "thinkingBudget": 1024 # Limit thinking to 1024 tokens to save time
            }
        }
    }

    print(f"正在呼叫原生 Gemini API ({model})...")
    print("-" * 50)
    
    response = requests.post(url, headers=headers, json=payload)
    
    if response.status_code == 200:
        data = response.json()
        
        try:
            # Extract reasoning/thinking and the final text
            parts = data['candidates'][0]['content']['parts']
            
            thinking_text = None
            final_text = None
            
            # parts usually contains multiple elements if thinking is included
            for part in parts:
                if 'thought' in part:
                    thinking_text = part['thought']
                elif 'text' in part:
                    final_text = part['text']
            
            if thinking_text:
                print("🧠 [大腦思考過程 (Reasoning)]:")
                print(thinking_text)
                print("-" * 50)
            else:
                print("⚠️ 模型回傳結果，但未包含思考過程。它可能把整段當作一般文本回覆了，或者該模型預設不回傳 thought 區塊。以下為完整 Raw JSON:")
                print(json.dumps(parts, indent=2, ensure_ascii=False))
                print("-" * 50)
                
            if final_text:
                print("🗣️ [最終回答 (Final Answer)]:")
                print(final_text)
            
        except KeyError as e:
            print(f"Failed to parse known structure. Raw JSON:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
            
    else:
        print(f"API Error ({response.status_code}):")
        print(response.text)

if __name__ == "__main__":
    main()
