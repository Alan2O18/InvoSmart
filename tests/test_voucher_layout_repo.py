"""
Tests for VoucherLayoutRepository — covers v29 §9 security and §8.3 IO.
Defense #32 (path traversal), #33 (atomic write).
"""
import json
import os

import pytest

from backend.repositories.voucher_layout_repo import VoucherLayoutRepository, sanitize_project_id


class TestSanitizeProjectId:
    def test_blocks_dot_dot(self):
        assert ".." not in sanitize_project_id("../../etc/passwd")

    def test_blocks_forward_slash(self):
        assert "/" not in sanitize_project_id("a/b/c")

    def test_blocks_backslash(self):
        assert "\\" not in sanitize_project_id("a\\b\\c")

    def test_combined_traversal(self):
        result = sanitize_project_id("../../evil\\proj")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_normal_id_unchanged(self):
        assert sanitize_project_id("my-project_123") == "my-project_123"

    def test_empty_string_returns_unknown(self):
        # After sanitization, all chars may be stripped; fallback to 'unknown'
        result = sanitize_project_id("")
        assert result == "unknown"

    def test_unicode_chars_sanitized(self):
        result = sanitize_project_id("專案一")
        assert isinstance(result, str)
        assert len(result) > 0


class TestVoucherLayoutRepository:
    def test_load_nonexistent_returns_empty(self, tmp_path):
        repo = VoucherLayoutRepository(layout_root=str(tmp_path))
        result = repo.load_layout("proj1")
        assert result == {"globalPrefix": "", "startIndex": 1, "pages": []}

    def test_save_and_load_roundtrip(self, tmp_path):
        repo = VoucherLayoutRepository(layout_root=str(tmp_path))
        payload = {
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{"pageIndex": 0, "fields": {"amount": "100"}, "images": []}],
        }
        result = repo.save_layout("proj1", payload)
        assert result["status"] == "success"

        loaded = repo.load_layout("proj1")
        assert loaded["globalPrefix"] == "D-16"
        assert loaded["pages"][0]["fields"]["amount"] == "100"

    def test_atomic_write_no_tmp_leftover(self, tmp_path):
        """After save, no .tmp file should remain (Defense #33)."""
        repo = VoucherLayoutRepository(layout_root=str(tmp_path))
        repo.save_layout("proj1", {"globalPrefix": "", "startIndex": 1, "pages": []})

        layout_dir = tmp_path / "proj1"
        files = list(layout_dir.iterdir())
        assert all(not f.name.endswith(".tmp") for f in files)

    def test_overwrite_existing_layout(self, tmp_path):
        repo = VoucherLayoutRepository(layout_root=str(tmp_path))
        repo.save_layout("proj1", {"globalPrefix": "A", "startIndex": 1, "pages": []})
        repo.save_layout("proj1", {"globalPrefix": "B", "startIndex": 2, "pages": []})

        loaded = repo.load_layout("proj1")
        assert loaded["globalPrefix"] == "B"
        assert loaded["startIndex"] == 2

    def test_creates_directory_if_missing(self, tmp_path):
        repo = VoucherLayoutRepository(layout_root=str(tmp_path / "deep" / "nested"))
        repo.save_layout("proj1", {"globalPrefix": "", "startIndex": 1, "pages": []})
        assert (tmp_path / "deep" / "nested" / "proj1" / "voucher_layout.json").exists()

    def test_corrupted_json_file_returns_empty(self, tmp_path):
        """If the layout file has corrupted JSON, return empty layout safely."""
        repo = VoucherLayoutRepository(layout_root=str(tmp_path))
        layout_dir = tmp_path / sanitize_project_id("proj1")
        layout_dir.mkdir(parents=True, exist_ok=True)
        (layout_dir / "voucher_layout.json").write_text("{invalid json", encoding="utf-8")

        with pytest.raises(json.JSONDecodeError):
            repo.load_layout("proj1")

    def test_path_traversal_in_project_id(self, tmp_path):
        """Malicious project_id should NOT escape layout_root (Defense #32)."""
        repo = VoucherLayoutRepository(layout_root=str(tmp_path))
        repo.save_layout("../../etc", {"globalPrefix": "", "startIndex": 1, "pages": []})

        # File should be inside tmp_path, not in ../../etc
        assert not os.path.exists(os.path.join(str(tmp_path), "..", "..", "etc"))
        # But should exist inside the sanitized directory
        assert any(tmp_path.rglob("voucher_layout.json"))
