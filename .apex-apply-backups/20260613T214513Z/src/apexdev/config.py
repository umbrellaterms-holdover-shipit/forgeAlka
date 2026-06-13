from __future__ import annotations

"""Local configuration helpers for Apex.

Secrets are file-backed by default. The OpenRouter key lives in a small chmod
0600 text file instead of being smeared across shell profiles, Codespaces env
configuration, or command history.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os
import stat

DEFAULT_CONFIG_DIR = Path(os.environ.get("APEX_CONFIG_DIR", "~/.config/apex")).expanduser()
DEFAULT_PROVIDER = "openrouter"


@dataclass(frozen=True)
class SecretStatus:
    provider: str
    path: Path
    exists: bool
    readable: bool
    size_bytes: int | None = None
    mode: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "path": str(self.path),
            "exists": self.exists,
            "readable": self.readable,
            "size_bytes": self.size_bytes,
            "mode": self.mode,
        }


def config_dir() -> Path:
    """Return the Apex config directory, creating nothing."""
    return DEFAULT_CONFIG_DIR


def secret_path(provider: str = DEFAULT_PROVIDER, path: str | Path | None = None) -> Path:
    """Return the secret file path for a provider.

    Provider names are intentionally narrow and boring. The default OpenRouter
    key file is `~/.config/apex/openrouter.key`.
    """
    if path is not None:
        return Path(path).expanduser()
    safe = provider.strip().lower().replace("/", "_").replace("\\", "_")
    if not safe:
        safe = DEFAULT_PROVIDER
    return config_dir() / f"{safe}.key"


def read_secret(provider: str = DEFAULT_PROVIDER, path: str | Path | None = None) -> str | None:
    """Read a provider secret from disk, returning None if absent or empty."""
    p = secret_path(provider, path)
    try:
        value = p.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def write_secret(value: str, provider: str = DEFAULT_PROVIDER, path: str | Path | None = None) -> Path:
    """Write a provider secret with private file permissions."""
    secret = value.strip()
    if not secret:
        raise ValueError("secret value is empty")
    p = secret_path(provider, path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(secret + "\n", encoding="utf-8")
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        # Some filesystems, especially mounted dev volumes, may not honor chmod.
        # The caller can inspect status.mode if they care.
        pass
    return p


def secret_status(provider: str = DEFAULT_PROVIDER, path: str | Path | None = None) -> SecretStatus:
    """Return non-secret metadata for a provider key file."""
    p = secret_path(provider, path)
    try:
        st = p.stat()
    except FileNotFoundError:
        return SecretStatus(provider=provider, path=p, exists=False, readable=False)
    readable = os.access(p, os.R_OK)
    mode = oct(stat.S_IMODE(st.st_mode))
    return SecretStatus(provider=provider, path=p, exists=True, readable=readable, size_bytes=st.st_size, mode=mode)


def resolve_api_key(
    *,
    explicit_key: str | None = None,
    provider: str = DEFAULT_PROVIDER,
    path: str | Path | None = None,
) -> str | None:
    """Resolve an API key.

    Order:
      1. Explicit key, useful for tests or one-off calls.
      2. File-backed key, the normal path.
    """
    if explicit_key:
        return explicit_key.strip()
    from_file = read_secret(provider, path)
    if from_file:
        return from_file
    return None
