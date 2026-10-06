import numpy as np

from ee_toolkit import validation as val
from ee_toolkit.acquisition import Frame, decode_frames, read_log, write_log
from ee_toolkit.cli import main
from ee_toolkit.simulator import EcuSimulator, Fault, demo_faults


def run(db, faults, duration=30.0, seed=0):
    frames = list(EcuSimulator(db, duration, seed, faults).frames())
    series = decode_frames(frames, db)
    return series, val.run_all(series, db)


def test_clean_run_passes(db):
    _, violations = run(db, [])
    assert violations == []


def test_frame_counts_follow_cycle_times(db):
    series, _ = run(db, [], duration=10.0)
    assert len(series["VehSpeed"][0]) == 500
    assert len(series["BattVoltage"][0]) == 100


def test_same_seed_is_reproducible(db):
    a = list(EcuSimulator(db, 2.0, 5).frames())
    b = list(EcuSimulator(db, 2.0, 5).frames())
    assert a == b


def test_dropout_detected_as_cycle_time(db):
    _, v = run(db, [Fault("dropout", "Battery", 8.0, 9.0)])
    assert [x.rule for x in v] == ["cycle_time"]
    assert v[0].target == "Battery" and v[0].t_end == 9.0


def test_out_of_range_detected(db):
    _, v = run(db, [Fault("out_of_range", "BattVoltage", 21.0, 21.5, value=17.5)])
    assert len(v) == 1 and v[0].rule == "range" and v[0].target == "BattVoltage"


def test_stuck_signal_detected(db):
    _, v = run(db, [Fault("stuck", "EngineRpm", 14.0, 18.0)])
    assert [x.rule for x in v] == ["stuck"]
    assert 3.9 <= v[0].t_end - v[0].t_start <= 4.0


def test_short_stuck_period_is_tolerated(db):
    _, v = run(db, [Fault("stuck", "EngineRpm", 14.0, 14.5)])
    assert v == []


def test_counter_skip_detected(db):
    _, v = run(db, [Fault("counter_skip", "AliveCounter", 25.0, 25.02)])
    assert v and all(x.rule == "counter" for x in v)


def test_counter_wraparound_is_not_a_violation():
    series = {"c": (np.arange(6.0), np.array([14, 15, 0, 1, 2, 3]))}
    assert val.check_counter(series, "c") == []


def test_all_demo_faults_found(db):
    _, v = run(db, demo_faults())
    assert {x.rule for x in v} == {"cycle_time", "stuck", "range", "counter"}


def test_log_roundtrip(db, tmp_path):
    frames = list(EcuSimulator(db, 1.0, 1).frames())
    write_log(frames, tmp_path / "x.csv")
    back = read_log(tmp_path / "x.csv")
    assert len(back) == len(frames)
    assert back[10].data == frames[10].data and back[10].can_id == frames[10].can_id


def test_decode_skips_unknown_and_malformed_frames(db):
    good = list(EcuSimulator(db, 0.1, 0).frames())
    bad = [Frame(0.0, 0x7FF, b"\x00"), Frame(0.0, 0x100, b"\x00")]
    series = decode_frames(bad + good, db)
    assert len(series["VehSpeed"][0]) == 5


def test_cli_exit_codes(tmp_path, capsys):
    db_path = "config/vehicle_signals.json"
    clean, dirty = str(tmp_path / "c.csv"), str(tmp_path / "d.csv")
    assert main(["--db", db_path, "simulate", "--faults", "none", "--out", clean]) == 0
    assert main(["--db", db_path, "simulate", "--faults", "demo", "--out", dirty]) == 0
    assert main(["--db", db_path, "validate", clean]) == 0
    assert main(["--db", db_path, "validate", dirty]) == 1
    assert "FAIL" in capsys.readouterr().out


def test_report_is_written(tmp_path):
    out = tmp_path / "r.html"
    log = str(tmp_path / "d.csv")
    main(["--db", "config/vehicle_signals.json", "simulate", "--out", log])
    assert main(["--db", "config/vehicle_signals.json", "report", log, "--out", str(out)]) == 0
    text = out.read_text()
    assert "FAIL" in text and "data:image/png;base64" in text
