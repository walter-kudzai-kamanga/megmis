"""Gen 4 object storage for audio/evidence with retention policies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from megmis.common.observability import metrics
from megmis.config import get_settings

log = logging.getLogger("megmis.storage")


@dataclass
class StoredObject:
    key: str
    uri: str
    bytes: int
    content_type: str
    retention_days: int
    expires_at: str


class ObjectStore(Protocol):
    def put(
        self,
        data: bytes,
        *,
        key: str | None = None,
        prefix: str = "audio",
        content_type: str = "application/octet-stream",
        retention_days: int | None = None,
    ) -> StoredObject: ...

    def delete(self, key: str) -> bool: ...

    def purge_expired(self) -> dict: ...


class LocalObjectStore:
    """Filesystem-backed store (default). Mimics S3 key layout under data/object-store/."""

    name = "local"

    def __init__(self, root: str | None = None) -> None:
        settings = get_settings()
        self.root = Path(root or settings.object_store_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.default_retention = settings.audio_retention_days

    def put(
        self,
        data: bytes,
        *,
        key: str | None = None,
        prefix: str = "audio",
        content_type: str = "application/octet-stream",
        retention_days: int | None = None,
    ) -> StoredObject:
        retention = retention_days if retention_days is not None else self.default_retention
        key = key or f"{prefix}/{datetime.now(UTC).strftime('%Y/%m/%d')}/{uuid4().hex}"
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        meta = {
            "content_type": content_type,
            "retention_days": retention,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (datetime.now(UTC) + timedelta(days=retention)).isoformat(),
            "bytes": len(data),
        }
        path.with_suffix(path.suffix + ".meta.json").write_text(
            __import__("json").dumps(meta), encoding="utf-8"
        )
        metrics.incr("object_store_puts", backend=self.name, prefix=prefix)
        return StoredObject(
            key=key,
            uri=f"file://{path}",
            bytes=len(data),
            content_type=content_type,
            retention_days=retention,
            expires_at=meta["expires_at"],
        )

    def delete(self, key: str) -> bool:
        path = self.root / key
        meta = path.with_suffix(path.suffix + ".meta.json")
        ok = False
        if path.exists():
            path.unlink()
            ok = True
        if meta.exists():
            meta.unlink()
            ok = True
        return ok

    def purge_expired(self) -> dict:
        now = datetime.now(UTC)
        removed = 0
        scanned = 0
        for meta_path in self.root.rglob("*.meta.json"):
            scanned += 1
            try:
                meta = __import__("json").loads(meta_path.read_text(encoding="utf-8"))
                exp = datetime.fromisoformat(meta["expires_at"])
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=UTC)
                if exp <= now:
                    obj = meta_path.with_name(meta_path.name.replace(".meta.json", ""))
                    # meta file is like file.wav.meta.json → object is file.wav
                    candidate = Path(str(meta_path)[: -len(".meta.json")])
                    if candidate.exists():
                        candidate.unlink()
                    meta_path.unlink(missing_ok=True)
                    removed += 1
                    _ = obj
            except Exception as exc:  # noqa: BLE001
                log.warning("purge skip %s: %s", meta_path, exc)
        metrics.incr("object_store_purged", amount=float(removed))
        return {"scanned": scanned, "removed": removed, "backend": self.name}


class S3ObjectStore:
    """
    Optional S3/MinIO backend. Uses boto3 if installed; otherwise raises so
    factory falls back to local. Retention via object tag + lifecycle note.
    """

    name = "s3"

    def __init__(self) -> None:
        settings = get_settings()
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 not installed; pip install boto3") from exc
        self.bucket = settings.s3_bucket
        self.default_retention = settings.audio_retention_days
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            region_name=settings.s3_region or "us-east-1",
        )

    def put(
        self,
        data: bytes,
        *,
        key: str | None = None,
        prefix: str = "audio",
        content_type: str = "application/octet-stream",
        retention_days: int | None = None,
    ) -> StoredObject:
        retention = retention_days if retention_days is not None else self.default_retention
        key = key or f"{prefix}/{datetime.now(UTC).strftime('%Y/%m/%d')}/{uuid4().hex}"
        expires = datetime.now(UTC) + timedelta(days=retention)
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            Metadata={
                "retention_days": str(retention),
                "expires_at": expires.isoformat(),
            },
            Tagging=f"retention_days={retention}&purpose=evidence",
        )
        metrics.incr("object_store_puts", backend=self.name, prefix=prefix)
        uri = f"s3://{self.bucket}/{key}"
        return StoredObject(
            key=key,
            uri=uri,
            bytes=len(data),
            content_type=content_type,
            retention_days=retention,
            expires_at=expires.isoformat(),
        )

    def delete(self, key: str) -> bool:
        self.client.delete_object(Bucket=self.bucket, Key=key)
        return True

    def purge_expired(self) -> dict:
        # Lifecycle rules should handle S3; this is a soft scan helper.
        return {
            "scanned": 0,
            "removed": 0,
            "backend": self.name,
            "note": "configure bucket lifecycle for retention_days tag",
        }


_store: ObjectStore | None = None


def get_object_store() -> ObjectStore:
    global _store
    if _store is not None:
        return _store
    settings = get_settings()
    backend = (settings.object_store_backend or "local").lower()
    if backend == "s3":
        try:
            _store = S3ObjectStore()
            return _store
        except Exception as exc:  # noqa: BLE001
            log.warning("S3 store unavailable (%s); using local", exc)
    _store = LocalObjectStore()
    return _store


def reset_object_store() -> None:
    global _store
    _store = None


def mirror_local_file(path: str, *, prefix: str = "audio", retention_days: int | None = None) -> StoredObject:
    """Copy an existing local artefact into the object store."""
    p = Path(path)
    data = p.read_bytes()
    ctype = "audio/wav" if p.suffix == ".wav" else "audio/mpeg" if p.suffix == ".mp3" else "application/octet-stream"
    return get_object_store().put(
        data,
        prefix=prefix,
        content_type=ctype,
        retention_days=retention_days,
        key=f"{prefix}/{p.name}",
    )
