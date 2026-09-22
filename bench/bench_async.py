"""asyncio vs asyncio+uvloop vs trio, running identical code.

The usual comparison rewrites the workload per library, which measures the
rewrite as much as the runtime. anyio removes that: the same source runs on
asyncio and on trio, and uvloop is a drop-in event loop policy under asyncio.
So the only thing that changes between runs is the scheduler underneath.

Three workloads, chosen because they stress different parts of a loop:
  spawn    - create and join N tasks. Pure scheduling bookkeeping.
  yield    - N cooperative yields in one task. Context-switch cost.
  echo     - real TCP round trips over loopback. Socket readiness plumbing.
"""
from __future__ import annotations
import json, pathlib, statistics, subprocess, sys, time

# Repo root, not bench/. An earlier version resolved to bench/, so it looked for
# bench/.venv/bin/python and wrote to bench/results/ - neither of which exists if
# you follow the README. Every subprocess failed and the run produced no rows.
ROOT = pathlib.Path(__file__).resolve().parent.parent
# The interpreter running this script, so `.venv/bin/python bench/bench_async.py`
# measures the venv you just built rather than a path guessed from __file__.
PY = sys.executable
REPS, WARMUP = 5, 1

WORKLOAD = r'''
import json, sys, time
import anyio

BACKEND = sys.argv[1]
WORK = sys.argv[2]
N = int(sys.argv[3])

async def noop():
    pass

async def spawn():
    async with anyio.create_task_group() as tg:
        for _ in range(N):
            tg.start_soon(noop)

async def yield_():
    for _ in range(N):
        await anyio.sleep(0)

async def echo():
    async def server(client):
        async with client:
            while True:
                data = await client.receive()
                if not data:
                    break
                await client.send(data)
    listener = await anyio.create_tcp_listener(local_host="127.0.0.1", local_port=0)
    port = listener.extra(anyio.abc.SocketAttribute.local_address)[1]
    async with anyio.create_task_group() as tg:
        tg.start_soon(listener.serve, server)
        await anyio.sleep(0.05)
        stream = await anyio.connect_tcp("127.0.0.1", port)
        async with stream:
            payload = b"x" * 64
            for _ in range(N):
                await stream.send(payload)
                await stream.receive()
        tg.cancel_scope.cancel()

MAIN = {"spawn": spawn, "yield": yield_, "echo": echo}[WORK]

opts = {}
if BACKEND == "uvloop":
    opts = {"backend": "asyncio", "backend_options": {"use_uvloop": True}}
elif BACKEND == "asyncio":
    opts = {"backend": "asyncio", "backend_options": {"use_uvloop": False}}
else:
    opts = {"backend": "trio"}

t0 = time.perf_counter()
anyio.run(MAIN, **opts)
print(json.dumps({"ms": (time.perf_counter() - t0) * 1000}))
'''

SIZES = {"spawn": 50_000, "yield": 200_000, "echo": 5_000}
BACKENDS = ["asyncio", "uvloop", "trio"]

def once(backend, work, n):
    p = subprocess.run([PY, "-c", WORKLOAD, backend, work, str(n)],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:160]
    return json.loads(p.stdout.strip().splitlines()[-1])["ms"], None

def main():
    rows = []
    for work, n in SIZES.items():
        for backend in BACKENDS:
            for _ in range(WARMUP):
                once(backend, work, n)
            samples, err = [], None
            for _ in range(REPS):
                ms, err = once(backend, work, n)
                if ms is None:
                    break
                samples.append(ms)
            if not samples:
                rows.append({"workload": work, "n": n, "backend": backend,
                             "min_ms": None, "error": err})
                print(f"  {work:6} {backend:8} FAILED  {err}")
                continue
            r = {"workload": work, "n": n, "backend": backend,
                 "min_ms": round(min(samples), 2),
                 "median_ms": round(statistics.median(samples), 2),
                 "per_op_us": round(min(samples) * 1000 / n, 3), "error": None}
            rows.append(r)
            print(f"  {work:6} {backend:8} {r['min_ms']:9.2f} ms  "
                  f"{r['per_op_us']:7.3f} us/op", flush=True)
    (ROOT/"results"/"async.json").write_text(json.dumps({"reps": REPS, "rows": rows}, indent=2))
    print("\nwrote results/async.json")

if __name__ == "__main__":
    main()
