from pathlib import Path

import pytest

from ee_toolkit.signals import SignalDatabase

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def db():
    return SignalDatabase.from_json(ROOT / "config" / "vehicle_signals.json")
