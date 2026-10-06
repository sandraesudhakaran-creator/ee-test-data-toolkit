"""Command line interface: simulate, validate, report."""
from __future__ import annotations

import argparse
import sys

from .acquisition import decode_frames, read_log, write_log
from .report import build_report
from .signals import SignalDatabase
from .simulator import EcuSimulator, demo_faults
from .validation import run_all


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="ee_toolkit", description=__doc__)
    p.add_argument("--db", default="config/vehicle_signals.json", help="signal database (JSON)")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="acquire from the simulated ECU network into a CSV log")
    s.add_argument("--out", default="logs/run.csv")
    s.add_argument("--duration", type=float, default=30.0)
    s.add_argument("--seed", type=int, default=0)
    s.add_argument("--faults", choices=["none", "demo"], default="demo")

    v = sub.add_parser("validate", help="run validation rules on a log; exit code 1 on failure")
    v.add_argument("log")

    r = sub.add_parser("report", help="validate a log and write an HTML report")
    r.add_argument("log")
    r.add_argument("--out", default="results/report.html")

    a = p.parse_args(argv)
    db = SignalDatabase.from_json(a.db)

    if a.cmd == "simulate":
        faults = demo_faults() if a.faults == "demo" else []
        n = write_log(EcuSimulator(db, a.duration, a.seed, faults).frames(), a.out)
        print(f"wrote {n} frames to {a.out}")
        return 0

    series = decode_frames(read_log(a.log), db)
    violations = run_all(series, db)
    if a.cmd == "validate":
        for x in violations:
            print(f"[{x.rule}] {x.target} {x.t_start:.2f}-{x.t_end:.2f}s: {x.detail}")
        print("PASS" if not violations else f"FAIL ({len(violations)} violations)")
        return 1 if violations else 0

    path = build_report(series, db, violations, f"Validation report: {a.log}", a.out)
    print(f"report written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
