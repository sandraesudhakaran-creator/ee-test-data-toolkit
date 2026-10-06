"""Signal and message definitions with CAN frame encoding and decoding.

Only little-endian (Intel) bit layout is supported. Signals are described in a
JSON signal database, similar in spirit to a DBC file but much smaller.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Signal:
    name: str
    start_bit: int
    length: int
    factor: float = 1.0
    offset: float = 0.0
    signed: bool = False
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None

    def decode(self, data: bytes) -> float:
        raw = (int.from_bytes(data, "little") >> self.start_bit) & ((1 << self.length) - 1)
        if self.signed and raw >> (self.length - 1):
            raw -= 1 << self.length
        return raw * self.factor + self.offset

    def to_raw(self, value: float) -> int:
        raw = round((value - self.offset) / self.factor)
        if self.signed:
            low, high = -(1 << (self.length - 1)), (1 << (self.length - 1)) - 1
        else:
            low, high = 0, (1 << self.length) - 1
        if not low <= raw <= high:
            raise ValueError(f"{self.name}: value {value} does not fit in {self.length} bits")
        return raw & ((1 << self.length) - 1)


@dataclass(frozen=True)
class Message:
    can_id: int
    name: str
    dlc: int
    cycle_time_ms: float
    signals: tuple[Signal, ...] = field(default_factory=tuple)

    def signal(self, name: str) -> Signal:
        for sig in self.signals:
            if sig.name == name:
                return sig
        raise KeyError(name)

    def encode(self, values: dict[str, float]) -> bytes:
        word = 0
        for sig in self.signals:
            if sig.name in values:
                word |= sig.to_raw(values[sig.name]) << sig.start_bit
        return word.to_bytes(self.dlc, "little")

    def decode(self, data: bytes) -> dict[str, float]:
        return {sig.name: sig.decode(data) for sig in self.signals}


class SignalDatabase:
    def __init__(self, messages: list[Message]):
        self.messages = {m.can_id: m for m in messages}
        self._owner = {s.name: m for m in messages for s in m.signals}

    @classmethod
    def from_dict(cls, raw: dict) -> "SignalDatabase":
        messages = []
        for m in raw["messages"]:
            sigs = tuple(Signal(**s) for s in m["signals"])
            messages.append(
                Message(int(m["id"], 0), m["name"], m["dlc"], m["cycle_time_ms"], sigs)
            )
        return cls(messages)

    @classmethod
    def from_json(cls, path: str | Path) -> "SignalDatabase":
        return cls.from_dict(json.loads(Path(path).read_text()))

    def message_for_signal(self, name: str) -> Message:
        return self._owner[name]

    def signal(self, name: str) -> Signal:
        return self._owner[name].signal(name)

    def signal_names(self) -> list[str]:
        return list(self._owner)
