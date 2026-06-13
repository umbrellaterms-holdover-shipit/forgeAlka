from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json, shutil, zipfile


@dataclass
class ArtifactBundle:
    root: Path
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def path(self) -> Path:
        return self.root / self.name

    def reset(self) -> Path:
        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir(parents=True)
        return self.path

    def write_text(self, rel: str, text: str) -> Path:
        target = self.path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def write_json(self, rel: str, data: Any) -> Path:
        return self.write_text(rel, json.dumps(data, indent=2, ensure_ascii=False))

    def zip_to(self, out_path: str | Path) -> Path:
        out = Path(out_path)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in sorted(self.path.rglob("*")):
                if file.is_file():
                    zf.write(file, file.relative_to(self.path.parent))
        return out
