"""Audio processing utilities using pydub.

This module provides basic functions for audio manipulation.  It
relies on the optional `pydub` library and an FFmpeg installation
to handle various audio formats.  Functions include concatenating
multiple audio files and slicing a segment from an audio file.
"""

from __future__ import annotations

from typing import Iterable
from pathlib import Path

try:
    from pydub import AudioSegment  # type: ignore
except ImportError as exc:  # pragma: no cover - optional dependency
    AudioSegment = None  # type: ignore
    _pydub_import_error = exc
else:
    _pydub_import_error = None


def concatenate_audios(audio_paths: Iterable[str | Path], output_path: str | Path) -> None:
    """Concatenate multiple audio files into a single file.

    Parameters
    ----------
    audio_paths:
        Iterable of paths to audio files to concatenate.
    output_path:
        Path of the output audio file.

    Raises
    ------
    ImportError
        If `pydub` is not installed.
    """
    if AudioSegment is None:
        raise ImportError(
            "pydub is required for audio concatenation but is not installed"
        ) from _pydub_import_error
    combined: AudioSegment | None = None
    for path in audio_paths:
        seg = AudioSegment.from_file(path)
        if combined is None:
            combined = seg
        else:
            combined += seg
    if combined is None:
        raise ValueError("No audio files provided")
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.export(str(out_path), format=out_path.suffix.lstrip('.'))


def slice_audio(audio_path: str | Path, start_ms: int, end_ms: int, output_path: str | Path) -> None:
    """Extract a slice from an audio file.

    Parameters
    ----------
    audio_path:
        Path to the input audio file.
    start_ms:
        Start position in milliseconds.
    end_ms:
        End position in milliseconds.
    output_path:
        Path to write the sliced audio file.

    Raises
    ------
    ImportError
        If `pydub` is not installed.
    """
    if AudioSegment is None:
        raise ImportError(
            "pydub is required for audio slicing but is not installed"
        ) from _pydub_import_error
    audio = AudioSegment.from_file(audio_path)
    slice_segment = audio[start_ms:end_ms]
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    slice_segment.export(str(out_path), format=out_path.suffix.lstrip('.'))