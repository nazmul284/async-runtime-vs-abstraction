"""Compare two runs of the same benchmark.

A single run tells you what the machine did once. Re-running the whole thing days
later on the same box and the same pinned versions tells you which of the numbers
you are allowed to quote to three significant figures - and which one is noise
wearing a decimal point.

    python bench/compare_runs.py results/runs/2026-09-14 results/runs/2026-09-22
"""
from __future__ import annotations
import json, pathlib, sys

def load(d, name, key):
    rows = json.loads((pathlib.Path(d) / name).read_text())["rows"]
    return {(r["workload"], r[key]): r["per_op_us"] for r in rows if r.get("per_op_us")}

def table(a_dir, b_dir, name, key, label):
    a, b = load(a_dir, name, key), load(b_dir, name, key)
    print(f"\n{label}  (us/op)")
    print(f"{'workload':10}{key:10}{pathlib.Path(a_dir).name:>12}"
          f"{pathlib.Path(b_dir).name:>12}{'drift':>9}")
    print("-" * 53)
    worst = (None, 0.0)
    for k in a:
        if k not in b: continue
        d = (b[k] - a[k]) / a[k] * 100
        flag = "  <-- unstable" if abs(d) > 10 else ""
        if abs(d) > abs(worst[1]): worst = (k, d)
        print(f"{k[0]:10}{k[1]:10}{a[k]:12.2f}{b[k]:12.2f}{d:+8.1f}%{flag}")
    return worst

if __name__ == "__main__":
    a_dir, b_dir = sys.argv[1], sys.argv[2]
    w1 = table(a_dir, b_dir, "async.json", "backend", "Through anyio")
    w2 = table(a_dir, b_dir, "async_raw.json", "loop", "Raw, no anyio")
    worst = max([w1, w2], key=lambda w: abs(w[1]))
    print(f"\nLargest drift: {worst[0][0]}/{worst[0][1]} at {worst[1]:+.1f}%. "
          "Anything above ~10% should be quoted as a range, not a figure.")
