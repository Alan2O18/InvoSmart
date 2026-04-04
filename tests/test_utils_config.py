from unittest.mock import patch

import backend.utils.config as config_module


def test_load_config_returns_empty_dict_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "_resolve_config_path", lambda: str(tmp_path / "missing.json"))

    assert config_module.load_config() == {}


def test_save_config_round_trips_through_disk(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    payload = {"project_manager_settings": {"workspace_root": "workspace"}}
    monkeypatch.setattr(config_module, "_resolve_config_path", lambda: str(config_path))

    assert config_module.save_config(payload) is True
    assert config_module.load_config() == payload


def test_save_config_returns_false_on_write_error(monkeypatch, tmp_path):
    monkeypatch.setattr(config_module, "_resolve_config_path", lambda: str(tmp_path / "config.json"))

    with patch("builtins.open", side_effect=PermissionError("denied")):
        assert config_module.save_config({"x": 1}) is False
