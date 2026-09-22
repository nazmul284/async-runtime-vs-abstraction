# async-runtime-vs-abstraction

asyncio vs uvloop vs trio, and the thing nobody measures: what the portability
layer on top costs compared with the event loop underneath.

Measured **2026-09-14** on Apple M2, 8 GB, macOS 26.6.2 (arm64), CPython 3.14.7.

## Picking a faster loop

```
workload              raw asyncio  raw uvloop   uvloop gain  unit
------------------------------------------------------------------------
spawn 50k tasks       2.53         1.85         1.37x        us/op
200k yields           13.90        12.98        1.07x        us/op
5k TCP round trips    45.94        23.95        1.92x        us/op

Raw asyncio against raw uvloop, no abstraction layer.
```

## Adding a portability layer

```
workload              raw asyncio  anyio/asyncio anyio adds    factor
----------------------------------------------------------------------------
spawn 50k tasks       2.53         15.13         +12.60 us     6.0x
200k yields           13.90        14.61         +0.71 us      1.1x
5k TCP round trips    45.94        107.50        +61.56 us     2.3x

Same event loop in both columns. The only difference is anyio.
```

Same event loop on both sides. The only difference is anyio, and on task spawning
it costs six times what the loop itself does.

## All three backends through anyio

```
workload              anyio/asyncio  anyio/uvloop  anyio/trio
----------------------------------------------------------------
spawn 50k tasks       15.13          13.08         13.87
200k yields           14.61          13.46         15.90
5k TCP round trips    107.50         69.99         70.99

Identical source on three backends. us/op, minimum of five runs.
```

Running through anyio, trio matches uvloop on I/O without any C extension.

## Method

- The three-backend comparison runs **identical source** on each backend. anyio
  makes that possible; rewriting the workload per library would measure the
  rewrite as much as the runtime.
- The raw control exists because the abstraction could be flattening the
  differences, and it is: uvloop's I/O advantage is 1.92x raw and 1.54x through
  anyio.
- Each measurement is a fresh subprocess. One warm-up, then five timed runs,
  minimum reported.
- Workloads: 50,000 task spawns, 200,000 cooperative yields, 5,000 TCP round
  trips of 64 bytes over loopback.

## Limits

- Loopback TCP is not a network. Real latency would dwarf these differences.
- Microbenchmarks. An application doing actual work per event will see a much
  smaller share of its time here.
- anyio is not the only abstraction layer, and its overhead is the price of
  portability, which may be worth paying.
- One machine, CPython 3.14.7. uvloop had no 3.15 wheel at time of writing.

## Reproducing

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python bench/bench_async.py        # three backends through anyio
.venv/bin/python bench/bench_async_raw.py    # raw control, no anyio
.venv/bin/python bench/tables.py             # the tables used in the article
```

## Reproducibility

The whole thing was re-run on **2026-09-22**, eight days after the first run, on the
same machine with the same pinned versions. Both snapshots are committed:

```bash
.venv/bin/python bench/compare_runs.py results/runs/2026-09-14 results/runs/2026-09-22
```

Eleven of twelve cells moved by less than 5%. One did not:

```
workload  loop        2026-09-14  2026-09-22    drift
-----------------------------------------------------
echo      asyncio          45.94       57.96   +26.2%  <-- unstable
echo      uvloop           23.95       24.89    +3.9%
spawn     asyncio           2.53        2.48    -2.1%
spawn     uvloop            1.85        1.83    -1.5%
yield     asyncio          13.90       13.72    -1.3%
yield     uvloop           12.98       12.66    -2.5%
```

So raw asyncio's TCP figure should be read as a range, roughly 46-58 us/op, not as a
number. uvloop's I/O advantage is correspondingly a range: **1.9x to 2.3x**, not 1.92x.

Everything the article argues survives the re-run. The layer-versus-loop ratio was 18.5x
on the first run and 17.1x on the second. And through anyio, trio came in 1% *behind*
uvloop on TCP the first time and 4% *ahead* the second, which is the useful result: on
this workload the two are indistinguishable, and quoting either direction as a win would
be over-reading the data.

MIT.
