from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json, math, random, struct, wave

@dataclass(slots=True)
class ChatterFragment:
    text: str
    speaker: str = "speaker"
    weight: float = 1.0
    tags: list[str] | None = None

@dataclass(slots=True)
class ScheduleItem:
    start_s: float
    duration_s: float
    speaker: str
    text: str
    pan: float = 0.0

def load_fragments(path: str | Path) -> list[ChatterFragment]:
    text = Path(path).read_text(encoding="utf-8")
    return [ChatterFragment(line.strip()) for line in text.splitlines() if line.strip()]

def generate_schedule(fragments: list[ChatterFragment], seed: int = 0, gap_range: tuple[float, float] = (0.4, 1.8)) -> list[ScheduleItem]:
    rng = random.Random(seed)
    t = 0.0
    schedule = []
    for frag in fragments:
        duration = max(0.8, min(12.0, len(frag.text.split()) * 0.38))
        schedule.append(ScheduleItem(round(t, 3), round(duration, 3), frag.speaker, frag.text, round(rng.uniform(-0.85, 0.85), 3)))
        t += duration + rng.uniform(*gap_range)
    return schedule

def write_schedule_json(schedule: list[ScheduleItem], path: str | Path) -> Path:
    out = Path(path)
    out.write_text(json.dumps([asdict(s) for s in schedule], indent=2, ensure_ascii=False), encoding="utf-8")
    return out

def render_tts_script(schedule: list[ScheduleItem]) -> str:
    return "\n".join(f"[{s.start_s:07.3f}s] {s.speaker}: {s.text}" for s in schedule)

def _tone(sample_rate: int, duration: float, freq: float, amp: float = 0.22) -> bytes:
    n = int(sample_rate * duration)
    vals = [int(32767 * amp * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n)]
    return struct.pack("<" + "h" * n, *vals)

def _silence(sample_rate: int, duration: float) -> bytes:
    n = int(sample_rate * duration)
    return struct.pack("<" + "h" * n, *([0] * n))

def write_placeholder_wav(schedule: list[ScheduleItem], path: str | Path, sample_rate: int = 22050) -> Path:
    out = Path(path)
    current = 0.0
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(sample_rate)
        for i, item in enumerate(schedule):
            if item.start_s > current:
                wf.writeframes(_silence(sample_rate, item.start_s - current)); current = item.start_s
            wf.writeframes(_tone(sample_rate, min(item.duration_s, 1.2), 330 + (i % 5) * 55))
            if item.duration_s > 1.2:
                wf.writeframes(_silence(sample_rate, item.duration_s - 1.2))
            current += item.duration_s
    return out
