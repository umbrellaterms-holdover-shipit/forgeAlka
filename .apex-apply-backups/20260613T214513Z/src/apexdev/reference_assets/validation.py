from __future__ import annotations
import py_compile
from pathlib import Path

def compile_embedded_source(path: str | Path) -> bool:
    py_compile.compile(str(path), doraise=True)
    return True
