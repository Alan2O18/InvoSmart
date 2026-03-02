import pytest
import sys

with open("test_err.log", "w", encoding="utf-8") as f:
    pytest.main(["tests/test_job_repository.py", "-q", "--tb=short", "--color=no"], stdout=f)
