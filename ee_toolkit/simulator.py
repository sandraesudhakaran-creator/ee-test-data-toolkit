"""Simulated ECU network: generates plausible CAN traffic with injectable faults."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np

from .acquisition import Frame
from .signals import SignalDatabase


@dataclass(frozen=True)
class Fault:
    kind: str            # "dropout" | "stuck" | "out_of_range" | "counter_skip"
    target: str          # message name (dropout) or signal name (others)
    t_start: float
    t_end: float
    value: float = 0.0   # used by out_of_range


def demo_faults() -> list[Fault]:
    return [
        Fault("dropout", "Battery", 8.0, 9.0),
        Fault("stuck", "EngineRpm", 14.0, 18.0),
        Fault("out_of_range", "BattVoltage", 21.0, 21.5, value=17.5),
        Fault("counter_skip", "AliveCounter", 25.0, 25.02),
    ]


class EcuSimulator:
    def __init__(self, db: SignalDatabase, duration_s: float = 30.0, seed: int = 0,
                 faults: list[Fault] | None = None):
        self.db, self.duration, self.faults = db, duration_s, faults or []
        self.rng = np.random.default_rng(seed)

    def _truth(self, t: float) -> dict[str, float]:
        speed = 60 + 40 * np.sin(2 * np.pi * t / 20.0)
        rpm = 900 + 28 * speed + self.rng.normal(0, 15)
        return {
            "VehSpeed": float(speed),
            "EngineRpm": float(rpm),
            "BattVoltage": 12.6 + 0.2 * np.sin(2 * np.pi * t / 7.0) + self.rng.normal(0, 0.01),
            "BattCurrent": 15 * np.sin(2 * np.pi * t / 11.0) + self.rng.normal(0, 0.3),
            "BattTemp": 25 + 0.5 * t / 10.0,
        }

    def _active(self, kind: str, target: str, t: float) -> Fault | None:
        for f in self.faults:
            if f.kind == kind and f.target == target and f.t_start <= t < f.t_end:
                return f
        return None

    def frames(self) -> Iterator[Frame]:
        stuck_values: dict[str, float] = {}
        counters = {m.can_id: 0 for m in self.db.messages.values()}
        events = []
        for msg in self.db.messages.values():
            step = msg.cycle_time_ms / 1000.0
            events += [(round(k * step, 6), msg) for k in range(int(self.duration / step))]
        for t, msg in sorted(events, key=lambda e: (e[0], e[1].can_id)):
            counters[msg.can_id] = (counters[msg.can_id] + 1) % 16
            if self._active("dropout", msg.name, t):
                continue
            values = self._truth(t)
            for sig in msg.signals:
                if sig.name == "AliveCounter":
                    c = counters[msg.can_id]
                    values[sig.name] = (c + 3) % 16 if self._active("counter_skip", sig.name, t) else c
                    continue
                if self._active("stuck", sig.name, t):
                    values[sig.name] = stuck_values.setdefault(sig.name, values[sig.name])
                else:
                    stuck_values.pop(sig.name, None)
                oor = self._active("out_of_range", sig.name, t)
                if oor:
                    values[sig.name] = oor.value
            yield Frame(t, msg.can_id, msg.encode({s.name: values[s.name] for s in msg.signals}))
