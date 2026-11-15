"""Gen 4 secret manager wiring — env first, optional file / vault-path stubs."""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol

log = logging.getLogger("megmis.secrets")


class SecretManager(Protocol):
    def get(self, name: str, default: str | None = None) -> str | None: ...


class EnvSecretManager:
    """Default: read from process environment (injected by compose/K8s/CI)."""

    name = "env"

    def get(self, name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, default)


class FileSecretManager:
    """
    Load secrets from a JSON file or directory of files (Docker/K8s secret mounts).
    Example: SECRET_MANAGER=file SECRET_FILE=/run/secrets/megmis.json
    """

    name = "file"

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._cache: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            log.warning("secret file missing: %s", self.path)
            return
        if self.path.is_dir():
            for child in self.path.iterdir():
                if child.is_file():
                    self._cache[child.name] = child.read_text(encoding="utf-8").strip()
            return
        raw = self.path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                self._cache = {str(k): str(v) for k, v in data.items()}
                return
        except json.JSONDecodeError:
            pass
        self._cache["default"] = raw.strip()

    def get(self, name: str, default: str | None = None) -> str | None:
        if name in self._cache:
            return self._cache[name]
        # fall through to env so mixed deployments work
        return os.environ.get(name, default)


class VaultPathStub:
    """
    Stub for HashiCorp Vault / cloud SM — resolves env `VAULT_ADDR` but only
    reads pre-injected env mirrors. Real HTTP Vault client is intentionally not
    required for Gen 4 local/dev; wire here when prod credentials exist.
    """

    name = "vault-stub"

    def get(self, name: str, default: str | None = None) -> str | None:
        mirrored = os.environ.get(f"VAULT_MIRROR_{name}", None)
        if mirrored is not None:
            return mirrored
        return os.environ.get(name, default)


@lru_cache
def get_secret_manager() -> SecretManager:
    from megmis.config import get_settings

    settings = get_settings()
    mode = (settings.secret_manager or "env").lower()
    if mode == "file" and settings.secret_file:
        return FileSecretManager(settings.secret_file)
    if mode in {"vault", "vault-stub"}:
        return VaultPathStub()
    return EnvSecretManager()


def secret(name: str, default: str | None = None) -> str | None:
    return get_secret_manager().get(name, default)
