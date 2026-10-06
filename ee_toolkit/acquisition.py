"""Frame sources, CSV logging and decoding of logs into signal time series.

`FrameSource` is the seam where real hardware would plug in (for example a
python-can bus). Only the simulated source is implemented here.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Protocol

import numpy as np

from .signals import SignalDatabase


@dataclass(frozen=True)
class Frame:
    timestamp: float
    can_id: int
    data: bytes


class FrameSource(Protocol):
    def frames(self) -> Iterator[Frame]: ...


def write_log(frames: Iterable[Frame], path: str | Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["timestamp", "can_id", "data_hex"])
        for f in frames:
            writer.writerow([f"{f.timestamp:.6f}", f"0x{f.can_id:X}", f.data.hex()])
            n += 1
    return n


def read_log(path: str | Path) -> list[Frame]:
    frames = []
    with Path(path).open(newline="") as fh:
        for row in csv.DictReader(fh):
            frames.append(
                Frame(float(row["timestamp"]), int(row["can_id"], 16), bytes.fromhex(row["data_hex"]))
            )
    return frames


def decode_frames(frames: Iterable[Frame], db: SignalDatabase) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Return {signal_name: (timestamps, values)} for all known messages."""
    times: dict[str, list[float]] = {n: [] for n in db.signal_names()}
    values: dict[str, list[float]] = {n: [] for n in db.signal_names()}
    for f in frames:
        msg = db.messages.get(f.can_id)
        if msg is None or len(f.data) != msg.dlc:
            continue  # unknown id or malformed frame: skipped, not fatal
        for name, val in msg.decode(f.data).items():
            times[name].append(f.timestamp)
            values[name].append(val)
    return {n: (np.array(times[n]), np.array(values[n])) for n in times}
