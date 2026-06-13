from __future__ import annotations

"""Small system-dependency helpers for Codespaces/devcontainer machines.

These helpers are intentionally boring: they check whether tools are on PATH,
print the exact install command that will be run, and only mutate the machine
when called by an explicit CLI command.
"""

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import os
import platform
import shutil
import subprocess
from typing import Iterable, Sequence

SUPPORTED_TOOLS = {"ffmpeg", "pandoc"}


@dataclass(frozen=True)
class ToolStatus:
    name: str
    present: bool
    path: str | None = None
    version: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _run_version(binary: str) -> str | None:
    try:
        proc = subprocess.run(
            [binary, "--version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=10,
        )
    except Exception:
        return None
    first = (proc.stdout or "").splitlines()
    return first[0].strip() if first else None


def check_tool(name: str) -> ToolStatus:
    """Return PATH/version status for a command-line tool."""
    path = shutil.which(name)
    return ToolStatus(name=name, present=path is not None, path=path, version=_run_version(path) if path else None)


def dependency_report(tools: Iterable[str] = ("ffmpeg", "pandoc")) -> list[ToolStatus]:
    """Return status rows for the requested tools."""
    return [check_tool(t) for t in tools]


def missing_tools(tools: Iterable[str] = ("ffmpeg", "pandoc")) -> list[str]:
    return [row.name for row in dependency_report(tools) if not row.present]


def _sudo_prefix() -> list[str]:
    if os.name == "nt" or os.geteuid() == 0:
        return []
    if shutil.which("sudo"):
        return ["sudo"]
    return []


def apt_install_command(tools: Iterable[str], assume_yes: bool = True) -> list[list[str]]:
    """Build apt-get commands for Linux/Codespaces.

    GitHub Codespaces/devcontainers are normally Debian/Ubuntu-flavored and
    have apt-get. This intentionally does not attempt exotic package-manager
    magic because silent cleverness is how dependency management grows teeth.
    """
    requested = [t for t in tools if t]
    unsupported = sorted(set(requested) - SUPPORTED_TOOLS)
    if unsupported:
        raise ValueError(f"Unsupported tools: {', '.join(unsupported)}. Supported: {', '.join(sorted(SUPPORTED_TOOLS))}")
    if not requested:
        return []
    if not shutil.which("apt-get"):
        raise RuntimeError("apt-get was not found. Automatic install is currently supported for Debian/Ubuntu/Codespaces only.")
    prefix = _sudo_prefix()
    install = prefix + ["apt-get", "install"]
    if assume_yes:
        install.append("-y")
    install.extend(requested)
    return [prefix + ["apt-get", "update"], install]


def install_system_tools(
    tools: Iterable[str] = ("ffmpeg", "pandoc"),
    *,
    assume_yes: bool = True,
    dry_run: bool = False,
    only_missing: bool = True,
) -> list[dict[str, object]]:
    """Install ffmpeg/pandoc using apt-get when possible.

    Returns a serializable log of commands and outcomes. On dry_run, no command
    is executed and the returned rows show what would run.
    """
    wanted = list(dict.fromkeys(tools))
    if only_missing:
        wanted = [t for t in wanted if not check_tool(t).present]
    commands = apt_install_command(wanted, assume_yes=assume_yes)
    log: list[dict[str, object]] = []
    for cmd in commands:
        row: dict[str, object] = {"command": cmd, "dry_run": dry_run}
        if dry_run:
            row.update({"returncode": None, "stdout": "", "stderr": ""})
        else:
            proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
            row.update({"returncode": proc.returncode, "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-4000:]})
            if proc.returncode != 0:
                log.append(row)
                raise RuntimeError(f"Command failed with exit {proc.returncode}: {' '.join(cmd)}\n{proc.stderr[-2000:]}")
        log.append(row)
    return log


def render_dependency_report(statuses: Sequence[ToolStatus]) -> str:
    lines = ["# Dependency Report", ""]
    for s in statuses:
        marker = "OK" if s.present else "MISSING"
        lines.append(f"- {s.name}: {marker}" + (f" ({s.version}; {s.path})" if s.present else ""))
    lines.append("")
    if any(not s.present for s in statuses):
        missing = " ".join(s.name for s in statuses if not s.present)
        lines.append(f"Install missing tools with: `apex deps install {missing} --yes`")
    return "\n".join(lines)


def write_dependency_report(path: str | Path, tools: Iterable[str] = ("ffmpeg", "pandoc")) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [s.to_dict() for s in dependency_report(tools)]
    if out.suffix.lower() == ".json":
        out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    else:
        out.write_text(render_dependency_report(dependency_report(tools)), encoding="utf-8")
    return out
