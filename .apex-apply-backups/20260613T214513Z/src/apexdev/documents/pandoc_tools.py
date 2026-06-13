from __future__ import annotations

"""Pandoc bridge.

Pandoc is the cleanest path for serious document conversion when the binary is
available. These helpers keep subprocess handling centralized and explicit.
"""

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PandocResult:
    input_path: Path
    output_path: Path
    command: list[str]
    stdout: str
    stderr: str


def pandoc_path() -> str | None:
    return shutil.which("pandoc")


def has_pandoc() -> bool:
    return pandoc_path() is not None


def require_pandoc() -> str:
    path = pandoc_path()
    if not path:
        raise RuntimeError("pandoc is required for this conversion. Install it with `apex deps install pandoc --yes`.")
    return path


def pandoc_convert(
    input_path: str | Path,
    output_path: str | Path,
    *,
    from_format: str | None = None,
    to_format: str | None = None,
    extra_args: Sequence[str] | None = None,
) -> PandocResult:
    """Convert one file using pandoc."""
    src = Path(input_path)
    dst = Path(output_path)
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [require_pandoc(), str(src), "-o", str(dst)]
    if from_format:
        cmd.extend(["--from", from_format])
    if to_format:
        cmd.extend(["--to", to_format])
    if extra_args:
        cmd.extend(extra_args)
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"pandoc failed with exit {proc.returncode}: {' '.join(cmd)}\n{proc.stderr}")
    return PandocResult(src, dst, cmd, proc.stdout, proc.stderr)


def pandoc_supported_message() -> str:
    if has_pandoc():
        return "pandoc found"
    return "pandoc missing; install with `apex deps install pandoc --yes`"
