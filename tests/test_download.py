import json
from pathlib import Path

import pytest

from argentina_retail_sales import config, download


class FakeResponse:
    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        assert chunk_size == 1024 * 1024
        yield b"official,data\n"


def test_download_writes_sources_and_manifest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    raw = tmp_path / "raw"
    manifests = tmp_path / "manifests"
    monkeypatch.setattr(config, "RAW_DIR", raw)
    monkeypatch.setattr(config, "PORTFOLIO_DATA_DIR", tmp_path / "portfolio_data")
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr(config, "MANIFEST_DIR", manifests)

    requested_urls = []

    def fake_get(url: str, **kwargs: object) -> FakeResponse:
        requested_urls.append(url)
        assert kwargs == {"stream": True, "timeout": (10, 60)}
        return FakeResponse()

    monkeypatch.setattr(download.requests, "get", fake_get)

    first_manifest = download.download_all()
    second_manifest = download.download_all()

    assert len(requested_urls) == len(config.SOURCES)
    assert len(first_manifest) == len(second_manifest) == len(config.SOURCES)
    assert all(row["sha256"] for row in first_manifest)
    manifest_rows = [
        json.loads(line)
        for line in (manifests / "raw_sources.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert {row["source"] for row in manifest_rows} == set(config.SOURCES)
