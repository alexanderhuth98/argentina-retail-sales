import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import requests

from . import config


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_all(force: bool = False) -> list[dict[str, object]]:
    config.ensure_directories()
    retrieved_at = datetime.now(UTC).isoformat()
    manifest: list[dict[str, object]] = []

    for source_name, source in config.SOURCES.items():
        destination = config.RAW_DIR / source["filename"]
        temporary = destination.with_suffix(destination.suffix + ".part")

        if force or not destination.exists():
            temporary.unlink(missing_ok=True)
            try:
                with requests.get(source["url"], stream=True, timeout=(10, 60)) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as output:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                output.write(chunk)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)

        manifest.append(
            {
                "source": source_name,
                "url": source["url"],
                "file": f"data/raw/{destination.name}",
                "retrieved_at": retrieved_at,
                "bytes": destination.stat().st_size,
                "sha256": _sha256(destination),
            }
        )

    manifest_path = config.MANIFEST_DIR / "raw_sources.jsonl"
    temporary_manifest = manifest_path.with_suffix(".jsonl.tmp")
    temporary_manifest.write_text(
        "".join(json.dumps(row, ensure_ascii=True) + "\n" for row in manifest),
        encoding="utf-8",
    )
    temporary_manifest.replace(manifest_path)
    return manifest
