import ollama

print(ollama.chat(model="qwen3-vl:2b", messages=[{"role": "user", "content": "Hello, how are you?"}]))