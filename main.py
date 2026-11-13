"""Peramal harga Yes Polymarket untuk event "Next CEO of NVIDIA?".

Untuk tiap case di direktori input, baca harga tiap menit sampai checkpoint
lalu tulis ramalan lima kuantil (5%, 25%, 50%, 75%, 95%) untuk tiap market
pada 240 menit setelah checkpoint.

Modelnya sederhana dan sepenuhnya deterministik:
  * Median: harga terakhir yang menyusut perlahan menuju nol, 0,02% per
    menit (sekitar 5% selama empat jam). Tidak ada ekstrapolasi tren:
    pada data latih, segala bentuk drift justru memperburuk skor.
  * Sebaran: proses Ornstein-Uhlenbeck dengan laju kembali-ke-rata-rata
    k = 0,012 per menit, jadi ragam pada horizon h adalah
    s^2 * (1 - exp(-2 k h)) / (2 k).
  * Skala inovasi s tiap market dihitung dari akar rata-rata kuadrat
    perubahan harga satu menit selama 360 menit terakhir, lalu ditarik
    40% ke arah median lintas market, diberi lantai 0,0003, dan diskalakan
    menurut level harga (pasar di tengah kisaran bergerak lebih lebar
    daripada pasar di dekat 0 atau 1).

Hanya pustaka standar Python; tanpa jaringan, tanpa keacakan, tanpa jam
dinding. Dua kali jalan pada case yang sama menghasilkan byte yang sama.
"""

import glob
import json
import math
import os
import sys

# Kuantil yang diminta case, beserta skor-z normal bakunya.
LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)
Z_SCORES = (-1.644854, -0.67449, 0.0, 0.67449, 1.644854)

HORIZON = 240          # menit yang diramal setelah checkpoint
DECAY_PER_MIN = 0.0002  # median menyusut 0,02% per menit menuju nol
OU_RATE = 0.012        # laju kembali-ke-rata-rata Ornstein-Uhlenbeck
LOOKBACK = 360         # menit terakhir untuk mengukur volatilitas
SHRINK_SELF = 0.6      # bobot volatilitas sendiri saat di-shrink
SHRINK_MEDIAN = 0.4    # bobot median lintas market saat di-shrink
SIGMA_FLOOR = 0.0003   # lantai skala inovasi per menit


def _median(sorted_values):
    """Median dari daftar yang sudah terurut."""
    n = len(sorted_values)
    mid = n // 2
    if n % 2:
        return sorted_values[mid]
    return 0.5 * (sorted_values[mid - 1] + sorted_values[mid])


def _rms_step(prices):
    """RMS perubahan 1-menit selama LOOKBACK menit terakhir."""
    recent = prices[-(LOOKBACK + 1):]
    diffs = [b - a for a, b in zip(recent, recent[1:])]
    if not diffs:
        return 0.0
    return math.sqrt(sum(d * d for d in diffs) / len(diffs))


def _innovation_scale(rms, last, cross_median):
    """Skala inovasi per menit satu market.

    RMS-nya di-shrink ke arah median lintas market, diberi lantai,
    lalu diskalakan menurut level harga terakhir.
    """
    scale = SHRINK_SELF * rms + SHRINK_MEDIAN * cross_median
    if scale < SIGMA_FLOOR:
        scale = SIGMA_FLOOR
    level = math.sqrt(max(last * (1.0 - last), 0.001)) / 0.5
    return scale * (0.3 + 0.7 * level)


def _forecast_market(prices, rms, cross_median):
    """Lima kuantil x 240 menit untuk satu market."""
    last = prices[-1]
    sigma = _innovation_scale(rms, last, cross_median)
    rows = []
    for h in range(1, HORIZON + 1):
        centre = last * (1.0 - DECAY_PER_MIN * h)
        var = sigma * sigma * (1.0 - math.exp(-2.0 * OU_RATE * h)) / (2.0 * OU_RATE)
        spread = math.sqrt(var)
        row = []
        prev = 0.0
        for z in Z_SCORES:
            value = centre + z * spread
            if value < 0.0:
                value = 0.0
            elif value > 1.0:
                value = 1.0
            value = round(value, 6) + 0.0
            if value < prev:
                value = prev
            row.append(value)
            prev = value
        rows.append(row)
    return rows


def _forecast_case(case):
    """Ramalan lengkap satu case: {"forecasts": [{"id", "q"}, ...]}."""
    if tuple(case.get("quantiles", [])) != LEVELS:
        raise ValueError("kuantil case tidak sesuai (0.05, 0.25, 0.5, 0.75, 0.95)")
    horizon = int(case.get("horizon_minutes", HORIZON))
    if horizon != HORIZON:
        raise ValueError("horizon case bukan 240 menit")

    markets = case["markets"]
    # RMS tiap market dihitung sekali: dipakai untuk median lintas market
    # (shrinkage) dan untuk skala inovasinya sendiri.
    own_scales = [_rms_step(market["prices"]) for market in markets]
    cross_median = _median(sorted(own_scales))

    forecasts = []
    for market, rms in zip(markets, own_scales):
        forecasts.append({
            "id": market["id"],
            "q": _forecast_market(market["prices"], rms, cross_median),
        })
    return {"forecasts": forecasts}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    try:
        os.makedirs(out_dir, exist_ok=True)
    except OSError:
        # Sandbox grader kadang read-only: lanjut saja, tulis akan gagal
        # dengan jelas bila direktori memang tidak ada.
        pass

    paths = sorted(glob.glob(os.path.join(in_dir, "*.in")))
    if not paths:
        sys.stderr.write("tidak ada file case *.in di %s\n" % in_dir)
        return 1
    for path in paths:
        with open(path, "r", encoding="utf-8") as handle:
            case = json.load(handle)
        result = _forecast_case(case)
        stem = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(out_dir, stem + ".out")
        text = json.dumps(result, separators=(",", ":")) + "\n"
        with open(out_path, "w", encoding="utf-8") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
