"""Control: is anyio flattening the differences between the loops?

The main run drives all three backends through anyio so the source is identical.
That is the fair comparison, but it also puts a layer between the benchmark and
the scheduler. If raw asyncio and raw uvloop differ by much more than they do
through anyio, then the abstraction is the thing being measured, not the loop.
"""
from __future__ import annotations
import json, pathlib, statistics, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
PY = str(ROOT / ".venv" / "bin" / "python")
REPS, WARMUP = 5, 1

SRC = r'''
import asyncio, json, sys, time
WORK, N, USE_UVLOOP = sys.argv[1], int(sys.argv[2]), sys.argv[3] == "uvloop"
if USE_UVLOOP:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

async def noop(): pass

async def spawn():
    await asyncio.gather(*[noop() for _ in range(N)])

async def yield_():
    for _ in range(N):
        await asyncio.sleep(0)

async def echo():
    async def handle(r, w):
        while True:
            d = await r.read(64)
            if not d: break
            w.write(d); await w.drain()
    srv = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = srv.sockets[0].getsockname()[1]
    r, w = await asyncio.open_connection("127.0.0.1", port)
    payload = b"x" * 64
    for _ in range(N):
        w.write(payload); await w.drain()
        await r.read(64)
    w.close(); await w.wait_closed()
    srv.close(); await srv.wait_closed()

MAIN = {"spawn": spawn, "yield": yield_, "echo": echo}[WORK]
t0 = time.perf_counter()
asyncio.run(MAIN())
print(json.dumps({"ms": (time.perf_counter() - t0) * 1000}))
'''

SIZES = {"spawn": 50_000, "yield": 200_000, "echo": 5_000}

def once(loop, work, n):
    p = subprocess.run([PY, "-c", SRC, work, str(n), loop],
                       capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        return None, (p.stderr or "").strip().splitlines()[-1][:160]
    return json.loads(p.stdout.strip().splitlines()[-1])["ms"], None

rows = []
for work, n in SIZES.items():
    for loop in ("asyncio", "uvloop"):
        for _ in range(WARMUP): once(loop, work, n)
        s = []
        for _ in range(REPS):
            ms, err = once(loop, work, n)
            if ms is None:
                print(f"  {work} {loop} FAILED {err}"); break
            s.append(ms)
        if not s: continue
        rows.append({"workload": work, "n": n, "loop": loop, "layer": "raw",
                     "min_ms": round(min(s), 2),
                     "per_op_us": round(min(s) * 1000 / n, 3)})
        print(f"  raw {work:6} {loop:8} {min(s):9.2f} ms  "
              f"{min(s)*1000/n:7.3f} us/op", flush=True)

(ROOT/"results"/"async_raw.json").write_text(json.dumps({"reps": REPS, "rows": rows}, indent=2))
print("\nwrote results/async_raw.json")
