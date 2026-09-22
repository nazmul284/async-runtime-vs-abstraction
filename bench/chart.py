"""The figure used in the article, generated from results/*.json.

There was previously a committed async.png with no script behind it, which meant
the chart could go stale against the data and nobody would know. This reads the
same JSON the tables read, so the two cannot disagree.

    python bench/chart.py
"""
from __future__ import annotations
import json, pathlib, sys
sys.path.insert(0, "/Users/nazmul/pp/medium_article/.claude/skills/medium-article/scripts")
import chartkit as ck
import matplotlib.pyplot as plt

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = json.loads((ROOT/"results"/"async_raw.json").read_text())["rows"]
LAY = json.loads((ROOT/"results"/"async.json").read_text())["rows"]

WORK = [("spawn", "spawn 50k tasks"), ("yield", "200k yields"), ("echo", "5k TCP round trips")]
SERIES = [
    ("raw asyncio",   ck.NEUTRAL, lambda w: g(RAW, w, "loop", "asyncio")),
    ("raw uvloop",    ck.BLUE,    lambda w: g(RAW, w, "loop", "uvloop")),
    ("anyio/asyncio", ck.VIOLET,  lambda w: g(LAY, w, "backend", "asyncio")),
    ("anyio/uvloop",  ck.AQUA,    lambda w: g(LAY, w, "backend", "uvloop")),
    # ORANGE, not CRITICAL: red is reserved in this palette for "failure / do not
    # do this", and trio is neither.
    ("anyio/trio",    ck.ORANGE,  lambda w: g(LAY, w, "backend", "trio")),
]

def g(rows, work, key, val):
    for r in rows:
        if r["workload"] == work and r.get(key) == val:
            return r.get("per_op_us")

def main():
    ck.use_style()
    fig, ax = ck.figure(8.8, 5.4)
    fig.subplots_adjust(left=0.20, right=0.955, top=0.785, bottom=0.165)
    n = len(SERIES); span = 0.80; h = span / n
    for i, (name, colour, get) in enumerate(SERIES):
        offs = span/2 - h/2 - i*h
        vals = [get(w) or 0 for w, _ in WORK]
        ck.barh(ax, [y + offs for y in range(len(WORK))], vals, height=h*0.86, color=colour)
        for y, v in zip(range(len(WORK)), vals):
            if v:
                ck.label(ax, v * 1.05, y + offs, f"{v:.1f}", size=7.4, color=ck.MUTED)
    ax.set_yticks(range(len(WORK))); ax.set_yticklabels([lbl for _, lbl in WORK])
    # Log scale: the workloads span 1.8 to 105 us/op, and on a linear axis the spawn
    # row - which carries the article's main finding - is an invisible sliver.
    ax.set_xscale("log")
    ax.set_xlim(1, 260)
    ax.set_xticks([1, 3, 10, 30, 100])
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:g}")
    # No axis label: it lands on the legend, and the subtitle already carries the unit.
    ck.frame(ax, "")
    ck.legend(ax, [ck.swatch(c) for _, c, _ in SERIES], [n for n, _, _ in SERIES], ncol=5, y=-0.06)
    ck.titles(fig, "The layer on top costs more than the loop underneath",
              "Microseconds per operation, log scale. Minimum of five runs, "
              "fresh subprocess each. CPython 3.14.7, Apple M2.")
    ck.footer(fig, "Code, both run snapshots and raw JSON: "
                   "github.com/nazmul284/async-runtime-vs-abstraction")
    fig.savefig(ROOT/"results"/"async.png", dpi=260); plt.close(fig)
    print("wrote results/async.png")

if __name__ == "__main__":
    main()
