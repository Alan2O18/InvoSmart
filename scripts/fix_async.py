import re
import sys

for file_path in sys.argv[1:]:
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
        
    # Safely convert setup, override, and simulated helpers that use awaits into async def
    text = re.sub(r'(\s+)def (setup_[a-zA-Z0-9_]+|override_[a-zA-Z0-9_]+|helper_[a-zA-Z0-9_]+|[_a-zA-Z0-9]*mock[a-zA-Z0-9_]*|simulate_[a-zA-Z0-9_]+)\(', r'\1async def \2(', text)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)
        
    print(f"{file_path} safely converted helper signatures.")
