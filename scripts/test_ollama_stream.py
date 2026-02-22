"""測試 Ollama streaming 回應格式"""
import ollama

print("測試 Ollama streaming 回應格式...")

try:
    stream = ollama.chat(
        model='qwen3:1.7b',
        messages=[{'role':'user','content':'hi'}],
        stream=True
    )
    
    for i, chunk in enumerate(stream):
        print(f"Chunk {i}: type={type(chunk)}")
        print(f"  內容: {chunk}")
        if i >= 2:
            break
            
except Exception as e:
    print(f"錯誤: {e}")
