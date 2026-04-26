import json

from backend.engine import voucher_text_config as config


def test_get_full_template_layout_uses_defaults_when_file_missing(monkeypatch, tmp_path):
    missing = tmp_path / "not_exists.json"
    monkeypatch.setattr(config, "_CONFIG_PATH", missing)

    payload = config.get_full_template_layout()

    assert payload["version"] == "0.0.9"
    assert "textFields" in payload
    assert "safeZone" in payload
    assert "blockedZones" in payload


def test_get_full_template_layout_loads_custom_json(monkeypatch, tmp_path):
    custom_path = tmp_path / "voucher_template_config.json"
    custom_path.write_text(
        json.dumps({"version": "9.9.9", "safeZone": {"x0": 1, "y0": 2, "x1": 3, "y1": 4}}, ensure_ascii=False),
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "_CONFIG_PATH", custom_path)

    payload = config.get_full_template_layout()

    assert payload["version"] == "9.9.9"
    assert payload["safeZone"]["x0"] == 1


def test_get_full_template_layout_fallback_on_invalid_json(monkeypatch, tmp_path):
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{invalid", encoding="utf-8")
    monkeypatch.setattr(config, "_CONFIG_PATH", bad_path)

    payload = config.get_full_template_layout()

    assert payload["version"] == "0.0.9"
    assert payload["font"]["url"] == "/api/voucher/fonts/kaiu.ttf"


def test_payload_accessors_return_expected_structures(monkeypatch, tmp_path):
    custom_path = tmp_path / "cfg.json"
    custom_path.write_text(json.dumps({"version": "1.2.3"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(config, "_CONFIG_PATH", custom_path)

    fields = config.get_text_field_config()
    payload = config.get_voucher_text_config_payload()

    assert "voucherNo" in fields
    assert payload["version"] == "1.2.3"
    assert "preview" in payload
