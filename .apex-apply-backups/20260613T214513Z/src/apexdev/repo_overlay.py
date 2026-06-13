from __future__ import annotations

"""Apply incoming files to matching files in a repository."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable
import hashlib
import shutil
import tempfile
import zipfile

_SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    ".apex-apply-backups",
}
_SKIP_FILES = {".DS_Store", "Thumbs.db"}


@dataclass(frozen=True)
class ApplyMatch:
    incoming_path: str
    target_path: str | None
    status: str
    method: str | None = None
    reason: str | None = None
    size_bytes: int | None = None
    backup_path: str | None = None
    score: float | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class IncomingFile:
    relative_path: str
    source_path: Path
    size_bytes: int

    @property
    def name(self) -> str:
        return Path(self.relative_path).name

    @property
    def suffix(self) -> str:
        return Path(self.relative_path).suffix.lower()

    @property
    def stem(self) -> str:
        return Path(self.relative_path).stem.lower()


def _is_safe_relative(path: str | Path) -> bool:
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts and str(p) not in {"", "."}


def _is_safe_zip_name(name: str) -> bool:
    return _is_safe_relative(name)


def _should_skip(path: Path) -> bool:
    return path.name in _SKIP_FILES or any(part in _SKIP_DIRS for part in path.parts)


def _repo_files(repo: Path) -> dict[str, Path]:
    rows: dict[str, Path] = {}
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if _should_skip(rel):
            continue
        rows[rel.as_posix()] = path
    return rows


def _incoming_from_file(source: Path) -> tuple[list[IncomingFile], tempfile.TemporaryDirectory[str] | None]:
    if _should_skip(Path(source.name)):
        return [], None
    return [IncomingFile(source.name, source, source.stat().st_size)], None


def _incoming_from_dir(source: Path) -> tuple[list[IncomingFile], tempfile.TemporaryDirectory[str] | None]:
    files: list[IncomingFile] = []
    for path in source.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(source)
        if _should_skip(rel):
            continue
        files.append(IncomingFile(rel.as_posix(), path, path.stat().st_size))
    return files, None


def _incoming_from_zip(source: Path) -> tuple[list[IncomingFile], tempfile.TemporaryDirectory[str]]:
    tmp = tempfile.TemporaryDirectory(prefix="apex_apply_")
    root = Path(tmp.name)
    files: list[IncomingFile] = []
    with zipfile.ZipFile(source) as zf:
        for info in zf.infolist():
            if info.is_dir() or not _is_safe_zip_name(info.filename):
                continue
            rel = Path(info.filename)
            if _should_skip(rel):
                continue
            out = root / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, out.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            files.append(IncomingFile(rel.as_posix(), out, out.stat().st_size))
    return files, tmp


def collect_incoming_files(source: str | Path) -> tuple[list[IncomingFile], tempfile.TemporaryDirectory[str] | None]:
    source = Path(source)
    if source.is_dir():
        return _incoming_from_dir(source)
    if source.is_file() and zipfile.is_zipfile(source):
        return _incoming_from_zip(source)
    if source.is_file():
        return _incoming_from_file(source)
    raise ValueError(f"source must be a folder, zip file, or ordinary file: {source}")


def _strip_common_root(paths: Iterable[str]) -> dict[str, str]:
    paths = list(paths)
    if len(paths) <= 1:
        return {p: p for p in paths}
    first_parts = [Path(p).parts[0] for p in paths if len(Path(p).parts) > 1]
    if not first_parts or len(first_parts) != len(paths):
        return {p: p for p in paths}
    root = first_parts[0]
    if any(part != root for part in first_parts):
        return {p: p for p in paths}
    return {p: Path(*Path(p).parts[1:]).as_posix() for p in paths}


def _normalized(s: str) -> str:
    return s.replace("\\", "/").strip("/").lower()


def _path_candidates(incoming: IncomingFile, stripped_rel: str) -> list[str]:
    rows: list[str] = []
    for rel in (incoming.relative_path, stripped_rel, incoming.name):
        rel = rel.strip("/")
        if rel and rel not in rows:
            rows.append(rel)
    return rows


def _unique(candidates: list[str], *, ambiguous_prefix: str) -> tuple[str | None, str | None]:
    unique = sorted(set(candidates))
    if len(unique) == 1:
        return unique[0], None
    if len(unique) > 1:
        return None, f"{ambiguous_prefix}: {', '.join(unique[:8])}"
    return None, None


def _unique_by_suffix(repo_map: dict[str, Path], suffix: str) -> tuple[str | None, str | None]:
    suffix_norm = _normalized(suffix)
    matches = [rel for rel in repo_map if _normalized(rel) == suffix_norm or _normalized(rel).endswith("/" + suffix_norm)]
    return _unique(matches, ambiguous_prefix="ambiguous suffix match")


def _unique_by_name(repo_map: dict[str, Path], name: str) -> tuple[str | None, str | None]:
    name_norm = name.lower()
    matches = [rel for rel in repo_map if Path(rel).name.lower() == name_norm]
    return _unique(matches, ambiguous_prefix="ambiguous name match")


def _unique_by_stem(repo_map: dict[str, Path], incoming: IncomingFile) -> tuple[str | None, str | None]:
    matches = [
        rel
        for rel in repo_map
        if Path(rel).suffix.lower() == incoming.suffix and Path(rel).stem.lower() == incoming.stem
    ]
    return _unique(matches, ambiguous_prefix="ambiguous stem match")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _unique_by_content(repo_map: dict[str, Path], incoming: IncomingFile) -> tuple[str | None, str | None]:
    incoming_hash = _sha256(incoming.source_path)
    matches = [rel for rel, path in repo_map.items() if path.stat().st_size == incoming.size_bytes and _sha256(path) == incoming_hash]
    return _unique(matches, ambiguous_prefix="ambiguous content match")


def _similarity_match(
    repo_map: dict[str, Path],
    incoming: IncomingFile,
    stripped_rel: str,
    *,
    threshold: float,
    same_extension: bool,
) -> tuple[str | None, str | None, float | None]:
    source_keys = [_normalized(x) for x in _path_candidates(incoming, stripped_rel)]
    scores: list[tuple[float, str]] = []
    for rel in repo_map:
        if same_extension and Path(rel).suffix.lower() != incoming.suffix:
            continue
        rel_norm = _normalized(rel)
        target_keys = [rel_norm, Path(rel_norm).name]
        score = max(SequenceMatcher(None, s, t).ratio() for s in source_keys for t in target_keys)
        if score >= threshold:
            scores.append((score, rel))
    scores.sort(reverse=True)
    if not scores:
        return None, None, None
    if len(scores) > 1 and scores[0][0] - scores[1][0] < 0.04:
        tied = [rel for score, rel in scores[:8] if scores[0][0] - score < 0.04]
        return None, f"ambiguous similarity match: {', '.join(tied)}", scores[0][0]
    return scores[0][1], None, scores[0][0]


def _explicit_target(target: str | None, repo_map: dict[str, Path], incoming_count: int) -> ApplyMatch | None:
    if target is None:
        return None
    if incoming_count != 1:
        raise ValueError("--target can only be used when the source resolves to one incoming file")
    if not _is_safe_relative(target):
        raise ValueError(f"unsafe target path: {target}")
    rel = Path(target).as_posix()
    if rel in repo_map:
        return ApplyMatch("", rel, "matched", "target")
    return ApplyMatch("", rel, "no_match", "target", "target does not exist; pass --create-missing to create it")


def match_incoming_file(
    incoming: IncomingFile,
    repo_map: dict[str, Path],
    stripped_rel: str,
    mode: str = "auto",
    *,
    fuzzy_threshold: float = 0.78,
    same_extension: bool = True,
    target: str | None = None,
    incoming_count: int = 1,
) -> ApplyMatch:
    explicit = _explicit_target(target, repo_map, incoming_count)
    if explicit is not None:
        return ApplyMatch(incoming.relative_path, explicit.target_path, explicit.status, explicit.method, explicit.reason, incoming.size_bytes)

    aliases = {"exact": "path", "basename": "name", "fuzzy": "similarity"}
    mode = aliases.get(mode, mode)
    allowed = {"auto", "path", "suffix", "name", "stem", "content", "similarity"}
    if mode not in allowed:
        raise ValueError(f"unknown match mode {mode!r}; expected one of {sorted(allowed)}")

    candidates = _path_candidates(incoming, stripped_rel)

    if mode in {"auto", "path"}:
        for rel in candidates:
            rel_norm = Path(rel).as_posix()
            if rel_norm in repo_map:
                return ApplyMatch(incoming.relative_path, rel_norm, "matched", "path", size_bytes=incoming.size_bytes)
        if mode == "path":
            return ApplyMatch(incoming.relative_path, None, "no_match", reason="no relative-path match", size_bytes=incoming.size_bytes)

    if mode in {"auto", "suffix"}:
        ambiguous: str | None = None
        for rel in candidates:
            found, reason = _unique_by_suffix(repo_map, rel)
            if found:
                return ApplyMatch(incoming.relative_path, found, "matched", "suffix", size_bytes=incoming.size_bytes)
            ambiguous = ambiguous or reason
        if mode == "suffix":
            return ApplyMatch(incoming.relative_path, None, "ambiguous" if ambiguous else "no_match", reason=ambiguous or "no suffix match", size_bytes=incoming.size_bytes)
        if ambiguous:
            return ApplyMatch(incoming.relative_path, None, "ambiguous", reason=ambiguous, size_bytes=incoming.size_bytes)

    if mode in {"auto", "name"}:
        found, reason = _unique_by_name(repo_map, incoming.name)
        if found:
            return ApplyMatch(incoming.relative_path, found, "matched", "name", size_bytes=incoming.size_bytes)
        if mode == "name":
            return ApplyMatch(incoming.relative_path, None, "ambiguous" if reason else "no_match", reason=reason or "no name match", size_bytes=incoming.size_bytes)
        if reason:
            return ApplyMatch(incoming.relative_path, None, "ambiguous", reason=reason, size_bytes=incoming.size_bytes)

    if mode in {"auto", "stem"}:
        found, reason = _unique_by_stem(repo_map, incoming)
        if found:
            return ApplyMatch(incoming.relative_path, found, "matched", "stem", size_bytes=incoming.size_bytes)
        if mode == "stem":
            return ApplyMatch(incoming.relative_path, None, "ambiguous" if reason else "no_match", reason=reason or "no stem match", size_bytes=incoming.size_bytes)
        if reason:
            return ApplyMatch(incoming.relative_path, None, "ambiguous", reason=reason, size_bytes=incoming.size_bytes)

    if mode in {"content"}:
        found, reason = _unique_by_content(repo_map, incoming)
        if found:
            return ApplyMatch(incoming.relative_path, found, "matched", "content", size_bytes=incoming.size_bytes)
        return ApplyMatch(incoming.relative_path, None, "ambiguous" if reason else "no_match", reason=reason or "no content match", size_bytes=incoming.size_bytes)

    if mode in {"similarity"}:
        found, reason, score = _similarity_match(repo_map, incoming, stripped_rel, threshold=fuzzy_threshold, same_extension=same_extension)
        if found:
            return ApplyMatch(incoming.relative_path, found, "matched", "similarity", size_bytes=incoming.size_bytes, score=score)
        return ApplyMatch(incoming.relative_path, None, "ambiguous" if reason else "no_match", reason=reason or "no similarity match", size_bytes=incoming.size_bytes, score=score)

    return ApplyMatch(incoming.relative_path, None, "no_match", reason="no matching existing file", size_bytes=incoming.size_bytes)


def _safe_create_target(stripped_rel: str, incoming: IncomingFile) -> str:
    rel = stripped_rel or incoming.relative_path
    if not _is_safe_relative(rel):
        raise ValueError(f"unsafe create path derived from incoming file: {incoming.relative_path}")
    return Path(rel).as_posix()


def apply_source(
    source: str | Path,
    *,
    repo: str | Path = ".",
    apply: bool = False,
    match_mode: str = "auto",
    backup_dir: str | Path | None = None,
    create_missing: bool = False,
    target: str | None = None,
    fuzzy_threshold: float = 0.78,
    cross_extension: bool = False,
) -> dict[str, object]:
    repo_path = Path(repo).resolve()
    repo_map = _repo_files(repo_path)
    incoming, cleanup = collect_incoming_files(source)
    stripped = _strip_common_root([f.relative_path for f in incoming])
    matches: list[ApplyMatch] = []
    backup_root: Path | None = None
    if apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_root = Path(backup_dir or (repo_path / ".apex-apply-backups" / stamp)).resolve()
        backup_root.mkdir(parents=True, exist_ok=True)
    try:
        by_rel = {f.relative_path: f for f in incoming}
        for item in incoming:
            match = match_incoming_file(
                item,
                repo_map,
                stripped.get(item.relative_path, item.relative_path),
                match_mode,
                fuzzy_threshold=fuzzy_threshold,
                same_extension=not cross_extension,
                target=target,
                incoming_count=len(incoming),
            )
            if match.status == "no_match" and create_missing:
                create_rel = target if target and len(incoming) == 1 else _safe_create_target(stripped.get(item.relative_path, item.relative_path), item)
                if not _is_safe_relative(create_rel):
                    raise ValueError(f"unsafe create path: {create_rel}")
                match = ApplyMatch(item.relative_path, Path(create_rel).as_posix(), "would_create", "create", size_bytes=item.size_bytes)

            if apply and match.status in {"matched", "would_create"} and match.target_path:
                target_path = repo_path / match.target_path
                backup_path: str | None = None
                if match.status == "matched" and target_path.exists() and backup_root:
                    backup = backup_root / match.target_path
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(target_path, backup)
                    backup_path = str(backup)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(by_rel[item.relative_path].source_path, target_path)
                repo_map[match.target_path] = target_path
                match = ApplyMatch(
                    match.incoming_path,
                    match.target_path,
                    "created" if match.status == "would_create" else "overwritten",
                    match.method,
                    match.reason,
                    match.size_bytes,
                    backup_path,
                    match.score,
                )
            matches.append(match)
    finally:
        if cleanup is not None:
            cleanup.cleanup()

    summary = {
        "source": str(Path(source)),
        "repo": str(repo_path),
        "applied": apply,
        "backup_dir": str(backup_root) if backup_root else None,
        "incoming_count": len(incoming),
        "matched_count": sum(1 for m in matches if m.status in {"matched", "overwritten"}),
        "overwritten_count": sum(1 for m in matches if m.status == "overwritten"),
        "would_create_count": sum(1 for m in matches if m.status == "would_create"),
        "created_count": sum(1 for m in matches if m.status == "created"),
        "ambiguous_count": sum(1 for m in matches if m.status == "ambiguous"),
        "no_match_count": sum(1 for m in matches if m.status == "no_match"),
    }
    return {"summary": summary, "matches": [m.to_dict() for m in matches]}
