from __future__ import annotations
from pathlib import Path

def write_trend_svg(values: list[float], out_path: str | Path, width: int = 640, height: int = 320) -> Path:
    out = Path(out_path)
    if not values:
        out.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
        return out
    maxv, minv = max(values), min(values)
    span = max(maxv - minv, 1e-9)
    pts = []
    for i, v in enumerate(values):
        x = 20 + (width - 40) * i / max(1, len(values) - 1)
        y = height - 20 - (height - 40) * (v - minv) / span
        pts.append(f"{x:.2f},{y:.2f}")
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}'><polyline fill='none' stroke='black' stroke-width='2' points='{' '.join(pts)}'/></svg>\n"
    out.write_text(svg, encoding="utf-8")
    return out
