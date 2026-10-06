"""Self-contained HTML report: violation table plus signal plots."""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .signals import SignalDatabase  # noqa: E402
from .validation import Series, Violation  # noqa: E402


def _plot(series: Series, db: SignalDatabase, violations: list[Violation]) -> str:
    names = [n for n in db.signal_names() if n != "AliveCounter"]
    fig, axes = plt.subplots(len(names), 1, figsize=(9, 1.7 * len(names)), sharex=True)
    for ax, name in zip(axes, names):
        t, v = series[name]
        ax.plot(t, v, lw=0.8, color="#1f3864")
        ax.set_ylabel(f"{name}\n[{db.signal(name).unit}]", fontsize=7)
        ax.tick_params(labelsize=7)
        for x in violations:
            if x.target in (name, db.message_for_signal(name).name):
                ax.axvspan(x.t_start, x.t_end + 0.05, color="#c0392b", alpha=0.25)
    axes[-1].set_xlabel("time [s]", fontsize=8)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def build_report(series: Series, db: SignalDatabase, violations: list[Violation],
                 title: str, path: str | Path) -> Path:
    verdict = "PASS" if not violations else "FAIL"
    rows = "".join(
        f"<tr><td>{html.escape(v.rule)}</td><td>{html.escape(v.target)}</td>"
        f"<td>{v.t_start:.2f} to {v.t_end:.2f} s</td><td>{html.escape(v.detail)}</td></tr>"
        for v in violations
    ) or "<tr><td colspan=4>No violations</td></tr>"
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:2em auto;color:#222}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:4px 8px;font-size:14px;text-align:left}}
.v{{font-weight:bold;color:{'#2e7d32' if verdict == 'PASS' else '#c0392b'}}}</style></head><body>
<h1>{html.escape(title)}</h1><p>Verdict: <span class="v">{verdict}</span> ({len(violations)} violations)</p>
<table><tr><th>Rule</th><th>Target</th><th>Time</th><th>Detail</th></tr>{rows}</table>
<h2>Signals</h2><img style="width:100%" src="data:image/png;base64,{_plot(series, db, violations)}">
</body></html>"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page)
    return path
