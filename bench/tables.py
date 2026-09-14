"""Render the article/README tables from the result JSON."""
from __future__ import annotations
import json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent / "results"
A = {(r["workload"], r["backend"]): r for r in json.loads((R/"async.json").read_text())["rows"]}
RAW = {(r["workload"], r["loop"]): r for r in json.loads((R/"async_raw.json").read_text())["rows"]}
WORKS = [("spawn","spawn 50k tasks"),("yield","200k yields"),("echo","5k TCP round trips")]

def row(c, w): return "".join(str(x).ljust(n) for x, n in zip(c, w)).rstrip()
def rule(w):   return "-" * sum(w)

def main_table() -> str:
    w = [22, 13, 13, 13, 11]
    out = [row(["workload","raw asyncio","raw uvloop","uvloop gain","unit"], w), rule(w)]
    for k, lab in WORKS:
        a, u = RAW[(k,"asyncio")]["per_op_us"], RAW[(k,"uvloop")]["per_op_us"]
        out.append(row([lab, f"{a:.2f}", f"{u:.2f}", f"{a/u:.2f}x", "us/op"], w))
    out += ["", "Raw asyncio against raw uvloop, no abstraction layer."]
    return "\n".join(out)

def layer_table() -> str:
    w = [22, 13, 14, 14, 13]
    out = [row(["workload","raw asyncio","anyio/asyncio","anyio adds","factor"], w), rule(w)]
    for k, lab in WORKS:
        a = RAW[(k,"asyncio")]["per_op_us"]; n = A[(k,"asyncio")]["per_op_us"]
        out.append(row([lab, f"{a:.2f}", f"{n:.2f}", f"+{n-a:.2f} us", f"{n/a:.1f}x"], w))
    out += ["", "Same event loop in both columns. The only difference is anyio."]
    return "\n".join(out)

def backend_table() -> str:
    w = [22, 15, 14, 13]
    out = [row(["workload","anyio/asyncio","anyio/uvloop","anyio/trio"], w), rule(w)]
    for k, lab in WORKS:
        out.append(row([lab] + [f"{A[(k,b)]['per_op_us']:.2f}" for b in ("asyncio","uvloop","trio")], w))
    out += ["", "Identical source on three backends. us/op, minimum of five runs."]
    return "\n".join(out)

if __name__ == "__main__":
    for n, f in (("RAW LOOPS", main_table), ("THE LAYER", layer_table), ("BACKENDS", backend_table)):
        print(f"\n===== {n} =====\n{f()}")
