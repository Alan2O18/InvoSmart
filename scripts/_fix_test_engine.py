"""Fix garbled Chinese folder names in tests/test_engine.py."""
import pathlib

target = pathlib.Path("tests/test_engine.py")
content = target.read_text(encoding="utf-8")

# Garbled strings (confirmed from repr output) -> correct folder names
replacements = [
    ("?\uee01?頛詨\uf16f", "原始輸入"),   # raw input dir
    ("?\uf24c\uf3f0?潛巨", "分割發票"),    # split output dir
]

for old, new in replacements:
    count = content.count(old)
    print(f"Replacing {repr(old)} -> {repr(new)} ({count} occurrences)")
    content = content.replace(old, new)

target.write_text(content, encoding="utf-8")
print("Done.")



