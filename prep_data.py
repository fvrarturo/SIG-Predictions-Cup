"""Turn the bot's recordings into the compact arrays make_figures.py reads.

The recorder wrote one gzip'd JSON-lines file per stream per UTC day. Two streams matter here:
  ext-YYYYMMDD       every 10 s, every market: our fair value plus Kalshi's and Polymarket's
                     200-contract depth prices
  sig_tops-YYYYMMDD  SIG's best bid and ask, polled every 0.8 s (hot markets) or 30 s (the rest)

Files are read one at a time, so memory stays around 300 MB. Output (in $SIG_DATA):
  series.npz    one sample a minute, Oct 1 - Nov 4 UTC, 237 markets: fair, kalshi, poly, sig_bid, sig_ask
  night.npz     the same every 10 s from Nov 3 22:00 to Nov 4 17:00 UTC (5 pm - noon ET)
  results.json  each market's result: SIG's settlement, else Kalshi's final result, else null
"""
import datetime as dt
import gzip
import json
import os
from pathlib import Path

import httpx
import numpy as np

ARCHIVE = Path(os.environ.get("SIG_ARCHIVE", "~/sigbot_data/server_logs/data")).expanduser()
OUT = Path(os.environ.get("SIG_DATA", "~/sigbot_data/writeup")).expanduser()
UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 1, tzinfo=UTC)
DAYS = 35                                          # Oct 1 .. Nov 4
NMIN = DAYS * 1440
N0, N1, STEP = dt.datetime(2026, 11, 3, 22, tzinfo=UTC), dt.datetime(2026, 11, 4, 17, tzinfo=UTC), 10
NN = int((N1 - N0).total_seconds()) // STEP

markets = json.load(open(OUT / "market_map.json"))["markets"]
ids = [m["sig_exchange_id"] for m in markets]
names = [f'{m["race_key"]}/{m["party"]}' for m in markets]
col = {e: i for i, e in enumerate(ids)}
M = len(ids)


def secs(line: bytes) -> int:
    """Seconds since T0 from the line's leading '{"ts":"2026-10-15T00:00:01...'."""
    s = line[7:26].decode()
    t = dt.datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]), int(s[11:13]), int(s[14:16]), int(s[17:19]), tzinfo=UTC)
    return int((t - T0).total_seconds())


def blank(n):
    return np.full((M, n), np.nan, dtype=np.float32)


ser = {k: blank(NMIN) for k in ("fair", "kalshi", "poly", "sig_bid", "sig_ask")}
night = {k: blank(NN) for k in ("fair", "kalshi", "poly", "sig_bid", "sig_ask")}
n0s = int((N0 - T0).total_seconds())


def num(v):
    return np.nan if v is None else v


for day in range(DAYS):
    d = (T0 + dt.timedelta(days=day)).strftime("%Y%m%d")

    # fair values: the first line of each minute, every line inside the night window
    last_min = -1
    with gzip.open(ARCHIVE / f"ext-{d}.jsonl.gz", "rb") as f:
        for line in f:
            s = secs(line)
            m = s // 60
            k = (s - n0s) // STEP
            in_night = 0 <= k < NN
            if (m == last_min or not 0 <= m < NMIN) and not in_night:
                continue
            rec = json.loads(line)["d"]
            for ex, v in rec.items():
                i = col.get(ex)
                if i is None:
                    continue
                vals = (num(v[0]), num(v[6]), num(v[10]))
                if m != last_min and 0 <= m < NMIN:
                    ser["fair"][i, m], ser["kalshi"][i, m], ser["poly"][i, m] = vals
                if in_night:
                    night["fair"][i, k], night["kalshi"][i, k], night["poly"][i, k] = vals
            last_min = m

    # SIG best prices: lines carry only the markets just polled, so keep a running book and
    # snapshot it at the first line of each new minute (and each new 10 s in the night window)
    state = {}
    cur_m = cur_k = -1
    with gzip.open(ARCHIVE / f"sig_tops-{d}.jsonl.gz", "rb") as f:
        for line in f:
            s = secs(line)
            m, k = s // 60, (s - n0s) // STEP
            if m != cur_m and 0 <= m < NMIN:
                for i, (b, a) in state.items():
                    ser["sig_bid"][i, m], ser["sig_ask"][i, m] = b, a
                cur_m = m
            if k != cur_k and 0 <= k < NN:
                for i, (b, a) in state.items():
                    night["sig_bid"][i, k], night["sig_ask"][i, k] = b, a
                cur_k = k
            for ex, v in json.loads(line)["d"].items():
                i = col.get(ex)
                if i is not None:
                    state[i] = (num(v[0]) or np.nan, num(v[1]) or np.nan)
    print(d, "done", flush=True)

np.savez_compressed(OUT / "series.npz", ids=ids, names=names, t0=str(T0), **ser)
np.savez_compressed(OUT / "night.npz", ids=ids, names=names, t0=str(N0), step=STEP, **night)

# results: SIG's own settlement first; Kalshi's finalized result for markets SIG hasn't settled
sig = {r["exchanges"][0]["id"]: r for r in json.load(open(OUT / "sig_results.json"))}
res = {}
for m in markets:
    r = sig.get(m["sig_exchange_id"])
    if r and r["status"] == "settled":
        res[m["sig_exchange_id"]] = {"y": 1.0 if r["settledWith"] == "YES" else 0.0, "src": "sig"}
todo = [m for m in markets if m["sig_exchange_id"] not in res]
if todo:
    tick = ",".join(m["kalshi"]["ticker"] for m in todo)
    km = httpx.get("https://api.elections.kalshi.com/trade-api/v2/markets", params={"tickers": tick, "limit": 200},
                   timeout=30).json()["markets"]
    by = {x["ticker"]: x for x in km}
    for m in todo:
        x = by.get(m["kalshi"]["ticker"], {})
        y = None
        if x.get("status") in ("finalized", "settled") and x.get("result") in ("yes", "no"):
            y = 1.0 if (x["result"] == "yes") == (m["kalshi"]["side"] == "yes") else 0.0
        res[m["sig_exchange_id"]] = {"y": y, "src": "kalshi" if y is not None else None}
json.dump({"names": dict(zip(ids, names)), "results": res}, open(OUT / "results.json", "w"))
print(sum(v["src"] == "sig" for v in res.values()), "settled by SIG,",
      sum(v["src"] == "kalshi" for v in res.values()), "by Kalshi,",
      sum(v["y"] is None for v in res.values()), "open")
