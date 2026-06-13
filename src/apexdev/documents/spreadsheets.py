from __future__ import annotations
from pathlib import Path
from typing import Iterable, Mapping, Any
import csv

def write_csv(path: str | Path, rows: Iterable[Mapping[str, Any]]) -> Path:
    rows = list(rows)
    out = Path(path)
    if not rows:
        out.write_text("", encoding="utf-8"); return out
    fields = list(rows[0].keys())
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    return out

def write_xlsx(path: str | Path, sheets: Mapping[str, Iterable[Mapping[str, Any]]]) -> Path:
    try:
        import openpyxl
    except ImportError as e:
        raise ImportError("openpyxl is required for write_xlsx") from e
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows_iter in sheets.items():
        rows = list(rows_iter)
        ws = wb.create_sheet(name[:31] or "Sheet")
        if rows:
            fields = list(rows[0].keys())
            ws.append(fields)
            for row in rows:
                ws.append([row.get(f) for f in fields])
    wb.save(path)
    return Path(path)
