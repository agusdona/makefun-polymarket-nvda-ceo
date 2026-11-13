#!/usr/bin/env python3
"""Polymarket NVIDIA CEO forecast: 240-minute quantiles from last price + volatility.

Median = last price (no drift). Spread grows like lognormal: sd(h) = s*sqrt((1-e^{-2k h})/(2k)).
s = max(0.7*rms360 + 0.3*rms60 shrunk towards the case median, FLOOR) * MULT, then levelled
by sqrt(max(x(1-x), MINV))/0.5. Per-price-bucket multipliers shape the quantiles.
Stdlib only, deterministic, no network.
"""
import json
import math
import os
import sys
from statistics import mean

W_LONG = 360
W_SHORT = 60
W_LONG_SHARE = 0.5
MEDIAN_SHARE = 0.3
FLOOR = 0.0003
MULT = 0.8
MINV = 0.001
LEVEL_SCALE = 0.5
K_DECAY = 0.008
HORIZON = 240

# (upper bound exclusive, multipliers for 0.05, 0.25, 0.5, 0.75, 0.95)
BUCKETS = [
    (0.02, (-2.303, -0.347, 0.0, 0.166, 4.682)),
    (0.08, (-1.854, -1.192, 0.0, 0.005, 3.365)),
    (0.25, (-1.151, -0.797, 0.0, 0.015, 1.721)),
    (1.01, (-2.648, -1.409, 0.0, 0.206, 1.721)),
]


def window_rms(changes, window):
    """Root-mean-square of the last `window` one-minute changes (0.0 if none)."""
    tail = changes[-window:] if window > 0 else []
    if not tail:
        return 0.0
    return math.sqrt(mean(c * c for c in tail))


def raw_sigma(prices_long):
    """Per-market raw volatility: 360-min and 60-min change RMS, each capped at its window."""
    deltas = [prices_long[i + 1] - prices_long[i] for i in range(len(prices_long) - 1)]
    long_w = min(W_LONG, len(deltas))
    short_w = min(W_SHORT, len(deltas))
    a = window_rms(deltas, long_w)
    b = window_rms(deltas, short_w)
    return W_LONG_SHARE * a + W_LONG_SHARE * b


def bucket_mults(x):
    for bound, mults in BUCKETS:
        if x < bound:
            return mults
    return BUCKETS[-1][1]


def snapped(v):
    """Clip to [0, 1], round half to 6 decimals, keep from -0.0."""
    v = min(1.0, max(0.0, v))
    return round(v * 1e6) / 1e6 + 0.0


def sigma_of(prices_long, med_sig):
    sig = max((1 - MEDIAN_SHARE) * raw_sigma(prices_long) + MEDIAN_SHARE * med_sig, FLOOR) * MULT
    x = prices_long[-1]
    lv = math.sqrt(max(x * (1 - x), MINV)) / 0.5
    return sig * (1 - LEVEL_SCALE + LEVEL_SCALE * lv)


def spread(h):
    return math.sqrt((1 - math.exp(-2 * K_DECAY * h)) / (2 * K_DECAY))


def rows_for(prices_long, med_sig):
    x = prices_long[-1]
    sig = sigma_of(prices_long, med_sig)
    mults = bucket_mults(x)
    out = []
    for h in range(1, HORIZON + 1):
        sd = sig * spread(h)
        row = sorted(snapped(x + m * sd) for m in mults)
        out.append(row)
    return out


def case_median(sigs):
    """Middle of the sorted raw sigmas; the mean of the two middles when even."""
    vals = sorted(sigs)
    n = len(vals)
    if n == 0:
        return 0.0
    mid = n // 2
    if n % 2:
        return vals[mid]
    return 0.5 * (vals[mid - 1] + vals[mid])


def forecast_case(markets):
    sigs = {m["id"]: raw_sigma(m["prices"]) for m in markets}
    med = case_median(list(sigs.values()))
    return {m["id"]: rows_for(m["prices"], med) for m in markets}


def read_case(path):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    return doc


def write_case(path, markets, rows_by_id):
    forecasts = [{"id": m["id"], "q": rows_by_id[m["id"]]} for m in markets]
    body = json.dumps({"forecasts": forecasts}, separators=(",", ":"), ensure_ascii=False) + "\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)


def run(in_dir, out_dir):
    names = sorted(n for n in os.listdir(in_dir) if n.endswith(".in"))
    for name in names:
        doc = read_case(os.path.join(in_dir, name))
        rows_by_id = forecast_case(doc["markets"])
        write_case(os.path.join(out_dir, name[:-3] + ".out"), doc["markets"], rows_by_id)


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    run(in_dir, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
