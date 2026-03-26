from pathlib import Path
from unittest.mock import AsyncMock, patch

import fitz
from PIL import Image


def test_generate_voucher_returns_pdf_file_response(mock_app_client, mock_engine_for_api, tmp_path):
    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"%PDF-1.4\n%mock template\n")
    output_root = tmp_path / "layouts"

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"image_path": str(tmp_path / "invoice.jpg")})
    mock_job_repo.get_display_result = AsyncMock(return_value={
        "summary": {"total": 456},
        "date": "2026/03/07",
        "items": [{"category": "茶水"}],
    })
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    generated_output = output_root / "proj1" / "outputs" / "voucher_123.pdf"

    def fake_generate_from_layout(pages, job_image_map, output_path):
        assert job_image_map == {"job-1": str(tmp_path / "invoice.jpg")}
        assert pages[0]["fields"]["amount"] == "456"
        assert pages[0]["fields"]["payDate"] == "2026-03-07"
        assert pages[0]["fields"]["receiptCount"] == "1"
        assert pages[0]["fields"]["purpose"] == "茶水"
        Path(output_path).write_bytes(b"%PDF-1.4\n%generated\n")

    payload = {
        "globalPrefix": "D-16",
        "startIndex": 1,
        "pages": [
            {
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "budgetItem": "茶水費",
                    "amount": "123",
                    "purpose": "茶水",
                    "receiptCount": "1",
                    "payDate": "2026-03-07",
                    "isManuallyEdited": False,
                },
                "images": [
                    {
                        "jobId": "job-1",
                        "x": 40,
                        "y": 400,
                        "w": 150,
                        "h": 150,
                    }
                ],
            }
        ],
    }

    with patch("backend.routers.voucher.get_voucher_settings", return_value={
        "template_pdf_path": str(template_path),
        "font_ttf_path": str(tmp_path / "kaiu.ttf"),
        "layout_root": str(output_root),
        "thumb_max_width": 800,
    }), patch("backend.routers.voucher.time.time", return_value=123), patch(
        "backend.routers.voucher.VoucherGenerator.generate_from_layout",
        side_effect=fake_generate_from_layout,
    ):
        response = mock_app_client.post("/api/voucher/proj1/generate", json=payload)

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"voucher_123.pdf\"" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-1.4")
    assert generated_output.exists()


def test_generate_keeps_manual_purpose_when_marked_edited(mock_app_client, mock_engine_for_api, tmp_path):
    template_path = tmp_path / "template.pdf"
    template_path.write_bytes(b"%PDF-1.4\n%mock template\n")
    output_root = tmp_path / "layouts"

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"image_path": str(tmp_path / "invoice.jpg")})
    mock_job_repo.get_display_result = AsyncMock(return_value={
        "summary": {"total": 200},
        "date": "2026-03-08",
        "items": [{"category": "應被覆蓋的用途"}],
    })
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    def fake_generate_from_layout(pages, job_image_map, output_path):
        assert pages[0]["fields"]["purpose"] == "手動用途"
        assert job_image_map == {"job-1": str(tmp_path / "invoice.jpg")}
        Path(output_path).write_bytes(b"%PDF-1.4\n%generated\n")

    payload = {
        "globalPrefix": "D-16",
        "startIndex": 1,
        "pages": [
            {
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "budgetItem": "茶水費",
                    "amount": "123",
                    "purpose": "手動用途",
                    "receiptCount": "1",
                    "payDate": "2026-03-07",
                    "isManuallyEdited": True,
                },
                "images": [
                    {
                        "jobId": "job-1",
                        "x": 40,
                        "y": 400,
                        "w": 150,
                        "h": 150,
                    }
                ],
            }
        ],
    }

    with patch("backend.routers.voucher.get_voucher_settings", return_value={
        "template_pdf_path": str(template_path),
        "font_ttf_path": str(tmp_path / "kaiu.ttf"),
        "layout_root": str(output_root),
        "thumb_max_width": 800,
    }), patch("backend.routers.voucher.time.time", return_value=456), patch(
        "backend.routers.voucher.VoucherGenerator.generate_from_layout",
        side_effect=fake_generate_from_layout,
    ):
        response = mock_app_client.post("/api/voucher/proj1/generate", json=payload)

    assert response.status_code == 200


def test_get_kaiu_font_returns_ttf_file(mock_app_client, tmp_path):
    font_path = tmp_path / "kaiu.ttf"
    font_path.write_bytes(b"mock-font")

    with patch("backend.routers.voucher.get_voucher_settings", return_value={
        "font_ttf_path": str(font_path),
    }):
        response = mock_app_client.get("/api/voucher/fonts/kaiu.ttf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "font/ttf"
    assert response.content == b"mock-font"


def test_get_voucher_text_config_returns_shared_field_map(mock_app_client):
    response = mock_app_client.get("/api/voucher/text-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "0.0.9"
    assert payload["font"]["url"] == "/api/voucher/fonts/kaiu.ttf"
    assert payload["fields"]["voucherNo"]["point"] == [78, 255]
    assert payload["fields"]["voucherNo"]["lineStep"] == 17
    assert payload["fields"]["voucherNo"]["maxLines"] == 5
    assert payload["fields"]["budgetItem"]["maxChars"] == 3
    assert payload["fields"]["amount"]["padLength"] == 6
    assert payload["fields"]["amount"]["digitPolicy"] == 6
    assert len(payload["fields"]["amount"]["xList"]) == 6
    assert payload["fields"]["paymentAmount"]["point"] == [310, 785]
    assert payload["fields"]["purpose"]["type"] == "textbox"
    # v0.0.9: response includes safeZone and blockedZones
    assert "safeZone" in payload
    assert payload["safeZone"]["x0"] == 30
    assert "blockedZones" in payload


def test_get_template_returns_done_invoices_with_result(mock_app_client, mock_engine_for_api, monkeypatch):
    mock_engine_for_api.project_repo.get_project = AsyncMock(
        return_value={"project_id": "proj1", "name": "Project 1", "created_at": "2026-01-01"}
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=[{"job_id": "j1", "status": "done"}])
    mock_job_repo.get_display_result = AsyncMock(return_value={"amount": "123"})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: {
            "template_pdf_path": __file__,
            "font_ttf_path": "",
            "layout_root": "./backend/data/projects",
            "max_pages": 10,
            "autosave_interval_sec": 30,
            "thumb_max_width": 800,
        },
    )
    monkeypatch.setattr(
        "backend.routers.voucher._template_preview_payload",
        lambda *_: {
            "templatePng": "mock_png",
            "pageWidth": 595.0,
            "pageHeight": 842.0,
            "previewPixelWidth": 1190,
            "previewPixelHeight": 1684,
        },
    )

    response = mock_app_client.get("/api/voucher/proj1/template")
    assert response.status_code == 200

    payload = response.json()
    assert payload["templatePng"] == "mock_png"
    assert payload["invoices"][0]["jobId"] == "j1"
    assert payload["invoices"][0]["result"]["amount"] == "123"


def test_layout_save_and_load(mock_app_client, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: {
            "template_pdf_path": "",
            "font_ttf_path": "",
            "layout_root": str(tmp_path),
            "max_pages": 10,
            "autosave_interval_sec": 30,
            "thumb_max_width": 800,
        },
    )

    save_resp = mock_app_client.post(
        "/api/voucher/proj1/layout",
        json={"globalPrefix": "", "startIndex": 1, "pages": [{"pageIndex": 0, "fields": {}, "images": []}]},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["status"] == "success"

    load_resp = mock_app_client.get("/api/voucher/proj1/layout")
    assert load_resp.status_code == 200
    assert load_resp.json()["pages"][0]["pageIndex"] == 0


def test_generate_rejects_unauthorized_jobid(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    template_pdf = tmp_path / "template.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(template_pdf)
    doc.close()

    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: {
            "template_pdf_path": str(template_pdf),
            "font_ttf_path": "",
            "layout_root": str(tmp_path),
            "max_pages": 10,
            "autosave_interval_sec": 30,
            "thumb_max_width": 800,
        },
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value=None)
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [
                {
                    "pageIndex": 0,
                    "fields": {
                        "voucherNo": "D-16-01",
                        "budgetItem": "",
                        "amount": "100",
                        "purpose": "餐費",
                        "receiptCount": "1",
                        "payDate": "2024-11-28",
                        "isManuallyEdited": False,
                    },
                    "images": [{"jobId": "foreign_job", "x": 30, "y": 394, "w": 100, "h": 100}],
                }
            ],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["error"] == "FORBIDDEN"


def test_generate_strict_amount_validation_422(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    template_pdf = tmp_path / "template.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(template_pdf)
    doc.close()

    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: {
            "template_pdf_path": str(template_pdf),
            "font_ttf_path": "",
            "layout_root": str(tmp_path),
            "max_pages": 10,
            "autosave_interval_sec": 30,
            "thumb_max_width": 800,
        },
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "x"})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [
                {
                    "pageIndex": 0,
                    "fields": {
                        "voucherNo": "D-16-01",
                        "budgetItem": "",
                        "amount": "1000000",
                        "purpose": "餐費",
                        "receiptCount": "1",
                        "payDate": "2024-11-28",
                        "isManuallyEdited": False,
                    },
                    "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
                }
            ],
        },
    )
    assert response.status_code == 422


def test_generate_returns_422_when_generator_rejects_amount_cells(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    template_pdf = _make_template_pdf(tmp_path)
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings(template_pdf, tmp_path),
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "x"})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    def _raise_value_error(*_args, **_kwargs):
        raise ValueError("Amount '1234567' exceeds voucher amount cells (6)")

    with patch("backend.routers.voucher.VoucherGenerator.generate_from_layout", side_effect=_raise_value_error):
        response = mock_app_client.post(
            "/api/voucher/proj1/generate",
            json={
                "globalPrefix": "D-16",
                "startIndex": 1,
                "pages": [
                    {
                        "pageIndex": 0,
                        "fields": {
                            "voucherNo": "D-16-01",
                            "budgetItem": "",
                            "amount": "123456",
                            "purpose": "餐費",
                            "receiptCount": "1",
                            "payDate": "2024-11-28",
                            "isManuallyEdited": False,
                        },
                        "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
                    }
                ],
            },
        )

    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "VALIDATION_ERROR"


def test_generate_success_returns_pdf_file(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    template_pdf = tmp_path / "template.pdf"
    image_path = tmp_path / "receipt.jpg"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(template_pdf)
    doc.close()

    Image.new("RGB", (300, 200), color=(255, 255, 255)).save(image_path)

    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: {
            "template_pdf_path": str(template_pdf),
            "font_ttf_path": "",
            "layout_root": str(tmp_path),
            "max_pages": 10,
            "autosave_interval_sec": 30,
            "thumb_max_width": 800,
        },
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": str(image_path)})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [
                {
                    "pageIndex": 0,
                    "fields": {
                        "voucherNo": "D-16-01",
                        "budgetItem": "帶動組",
                        "amount": "100",
                        "purpose": "餐費",
                        "receiptCount": "1",
                        "payDate": "2024-11-28",
                        "isManuallyEdited": False,
                    },
                    "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF")


def test_generate_missing_image_still_outputs_pdf(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    template_pdf = tmp_path / "template.pdf"

    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(template_pdf)
    doc.close()

    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: {
            "template_pdf_path": str(template_pdf),
            "font_ttf_path": "",
            "layout_root": str(tmp_path),
            "max_pages": 10,
            "autosave_interval_sec": 30,
            "thumb_max_width": 800,
        },
    )

    missing_path = str(tmp_path / "not_exists.jpg")
    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": missing_path})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [
                {
                    "pageIndex": 0,
                    "fields": {
                        "voucherNo": "D-16-01",
                        "budgetItem": "帶動組",
                        "amount": "100",
                        "purpose": "餐費",
                        "receiptCount": "1",
                        "payDate": "2024-11-28",
                        "isManuallyEdited": False,
                    },
                    "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
                }
            ],
        },
    )

    assert response.status_code == 200


# ── Additional tests per v29 §10.1 ─────────────────────────────────────────

def _make_voucher_settings(template_pdf, tmp_path):
    return {
        "template_pdf_path": str(template_pdf),
        "font_ttf_path": "",
        "layout_root": str(tmp_path),
        "max_pages": 10,
        "autosave_interval_sec": 30,
        "thumb_max_width": 800,
    }


def _make_template_pdf(tmp_path):
    template_pdf = tmp_path / "template.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(template_pdf)
    doc.close()
    return template_pdf


def test_layout_draft_accepts_empty_paydate(mock_app_client, monkeypatch, tmp_path):
    """v29 §10.1.6: payDate='' in Draft → 200."""
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings("", tmp_path),
    )

    response = mock_app_client.post(
        "/api/voucher/proj1/layout",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "amount": "",
                    "payDate": "",
                    "receiptCount": "",
                },
                "images": [],
            }],
        },
    )
    assert response.status_code == 200


def test_generate_strict_rejects_empty_paydate(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    """v29 §10.1.6: payDate='' in Strict → 422."""
    template_pdf = _make_template_pdf(tmp_path)
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings(template_pdf, tmp_path),
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "x"})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "budgetItem": "",
                    "amount": "100",
                    "purpose": "餐費",
                    "receiptCount": "1",
                    "payDate": "",
                    "isManuallyEdited": False,
                },
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
            }],
        },
    )
    assert response.status_code == 422


def test_generate_strict_rejects_decimal_amount(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    """Decimal amount like '100.5' → 422."""
    template_pdf = _make_template_pdf(tmp_path)
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings(template_pdf, tmp_path),
    )

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"job_id": "j1", "image_path": "x"})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "budgetItem": "",
                    "amount": "100.5",
                    "purpose": "餐費",
                    "receiptCount": "1",
                    "payDate": "2024-11-28",
                    "isManuallyEdited": False,
                },
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
            }],
        },
    )
    assert response.status_code == 422


def test_generate_strict_rejects_non_digit_amount(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    """Non-digit amount like 'abc' → 422."""
    template_pdf = _make_template_pdf(tmp_path)
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings(template_pdf, tmp_path),
    )

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "amount": "abc",
                    "receiptCount": "1",
                    "payDate": "2024-11-28",
                },
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 100, "h": 100}],
            }],
        },
    )
    assert response.status_code == 422


def test_generate_strict_rejects_zero_width_image(mock_app_client, mock_engine_for_api, monkeypatch, tmp_path):
    """Image with w=0 → 422."""
    template_pdf = _make_template_pdf(tmp_path)
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings(template_pdf, tmp_path),
    )

    response = mock_app_client.post(
        "/api/voucher/proj1/generate",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{
                "pageIndex": 0,
                "fields": {
                    "voucherNo": "D-16-01",
                    "amount": "100",
                    "receiptCount": "1",
                    "payDate": "2024-11-28",
                },
                "images": [{"jobId": "j1", "x": 30, "y": 394, "w": 0, "h": 100}],
            }],
        },
    )
    assert response.status_code == 422


def test_layout_draft_accepts_invalid_date(mock_app_client, monkeypatch, tmp_path):
    """Draft schema allows invalid date strings for autosave."""
    monkeypatch.setattr(
        "backend.routers.voucher.get_voucher_settings",
        lambda: _make_voucher_settings("", tmp_path),
    )

    response = mock_app_client.post(
        "/api/voucher/proj1/layout",
        json={
            "globalPrefix": "D-16",
            "startIndex": 1,
            "pages": [{
                "pageIndex": 0,
                "fields": {"payDate": "not-a-date", "amount": "100.5"},
                "images": [],
            }],
        },
    )
    assert response.status_code == 200
