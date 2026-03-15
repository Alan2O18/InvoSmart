from unittest.mock import AsyncMock


def test_voucher_image_thumb_uses_preview_cache(tmp_path, mock_app_client, mock_engine_for_api):
    source = tmp_path / "source.jpg"
    source.write_bytes(b"jpg")

    cached = tmp_path / "cached.webp"
    cached.write_bytes(b"webp-preview")

    mock_job_repo = AsyncMock()
    mock_job_repo.get_job = AsyncMock(return_value={"image_path": str(source)})
    mock_engine_for_api.get_job_repo.return_value = mock_job_repo

    mock_engine_for_api.file_ops.ensure_preview_cache = AsyncMock(
        return_value={"path": str(cached), "media_type": "image/webp", "cache_hit": True}
    )

    response = mock_app_client.get("/api/voucher/proj1/image/j1?thumb=true")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/webp")
    assert response.content == b"webp-preview"
    mock_engine_for_api.file_ops.ensure_preview_cache.assert_awaited_once_with("proj1", str(source), max_width=800)
