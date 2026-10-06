"""Rule-based validation of decoded signal data."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .signals import SignalDatabase

Series = dict[str, tuple[np.ndarray, np.ndarray]]


@dataclass(frozen=True)
class Violation:
    rule: str
    target: str
    t_start: float
    t_end: float
    detail: str


def _runs(mask: np.ndarray, t: np.ndarray) -> list[tuple[float, float, int]]:
    """Group consecutive True samples into (t_start, t_end, n_samples)."""
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append((float(t[i]), float(t[j]), j - i + 1))
            i = j + 1
        else:
            i += 1
    return out


def check_range(series: Series, db: SignalDatabase) -> list[Violation]:
    found = []
    for name, (t, v) in series.items():
        sig = db.signal(name)
        if sig.minimum is None and sig.maximum is None:
            continue
        lo = -np.inf if sig.minimum is None else sig.minimum
        hi = np.inf if sig.maximum is None else sig.maximum
        for a, b, n in _runs((v < lo) | (v > hi), t):
            worst = v[(t >= a) & (t <= b)]
            worst = worst[np.argmax(np.abs(worst - (lo + hi) / 2))]
            found.append(Violation("range", name, a, b, f"{n} samples outside [{lo}, {hi}], e.g. {worst:.3g} {sig.unit}"))
    return found


def check_cycle_time(series: Series, db: SignalDatabase, tolerance: float = 1.5) -> list[Violation]:
    found = []
    for msg in db.messages.values():
        t = series[msg.signals[0].name][0]
        limit = tolerance * msg.cycle_time_ms / 1000.0
        gaps = np.diff(t)
        for i in np.where(gaps > limit)[0]:
            found.append(Violation("cycle_time", msg.name, float(t[i]), float(t[i + 1]),
                                   f"gap {gaps[i] * 1000:.0f} ms, expected {msg.cycle_time_ms:g} ms"))
    return found


def check_stuck(series: Series, window_s: float = 2.0, signals: list[str] | None = None) -> list[Violation]:
    found = []
    for name in signals or []:
        t, v = series[name]
        if len(v) < 2:
            continue
        same = np.concatenate([[False], np.diff(v) == 0])
        for a, b, _ in _runs(same, t):
            if b - a >= window_s:
                found.append(Violation("stuck", name, a, b, f"value constant at {v[np.searchsorted(t, a)]:.4g} for {b - a:.1f} s"))
    return found


def check_counter(series: Series, name: str, modulus: int = 16) -> list[Violation]:
    t, v = series[name]
    steps = np.diff(v.astype(int)) % modulus
    return [
        Violation("counter", name, float(t[i]), float(t[i + 1]), f"counter step of {steps[i]}, expected 1")
        for i in np.where(steps != 1)[0]
    ]


def run_all(series: Series, db: SignalDatabase, stuck_signals: list[str] | None = None,
            counter_signals: list[str] | None = None) -> list[Violation]:
    v = check_range(series, db) + check_cycle_time(series, db)
    v += check_stuck(series, signals=stuck_signals if stuck_signals is not None else ["EngineRpm"])
    for name in counter_signals if counter_signals is not None else ["AliveCounter"]:
        v += check_counter(series, name)
    return sorted(v, key=lambda x: x.t_start)
