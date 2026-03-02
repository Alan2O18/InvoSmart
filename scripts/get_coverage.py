import sys
import contextlib
from unittest.mock import MagicMock

# Mock out cv2 and numpy to prevent Windows DLL caching collisions during tests
sys.modules['cv2'] = MagicMock()
sys.modules['numpy'] = MagicMock()

import pytest

with open("cov.log", "w", encoding="utf-8") as f:
    with contextlib.redirect_stdout(f):
        pytest.main([
            "tests/test_engine_word_exporter.py", 
            "-v", 
            "--cov=backend.engine.word_exporter", 
            "--cov-report=term-missing", 
            "--color=no"
        ])
