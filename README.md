# Peramal Harga "Next CEO of NVIDIA?" — make.fun

Entri untuk kompetisi `polymarket-nvidia-ceo-forecast-01`: meramal harga Yes
tiap market event Polymarket "Next CEO of NVIDIA?" pada 240 menit setelah
checkpoint, sebagai lima kuantil (5%, 25%, 50%, 75%, 95%) per menit.

## Cara jalan

```sh
MAKEFUN_INPUT_DIR=kit/polymarket-nvidia-ceo-forecast-01-kit/input \
MAKEFUN_OUTPUT_DIR=out \
python3 main.py
```

Membaca tiap `*.in` di direktori input (hanya dibaca, tidak ditulis) dan
menulis `<id>.out` yang sepadan. Hanya pustaka standar Python 3.13; tanpa
jaringan, tanpa keacakan. Runtime sekitar 0,1 detik per case, dan dua kali
jalan pada input yang sama menghasilkan byte yang identik.

## Model (ronde 2): Per-Bucket Calibrated Quantile Fan

- **Median**: harga terakhir, tanpa drift.
- **Volatilitas per market**: `s_raw = 0.5 * RMS(perubahan 1 menit, 360 menit terakhir) + 0.5 * RMS(..., 60 menit terakhir)`.
- **Shrink lintas market**: `s = max(0.7 * s_raw + 0.3 * median(s_raw) , 0.0003) * 0.8`.
- **Penyesuaian level harga** `x`: `lv = sqrt(max(x*(1-x), 0.001)) / 0.5`, lalu `s *= 0.5 + 0.5 * lv`.
- **Pertumbuhan sebaran** per horizon `h = 1..240`: `sd(h) = s * sqrt((1 - exp(-2*0.008*h)) / (2*0.008))`.
- **Pengali kuantil per bucket harga** untuk [0.05, 0.25, 0.5, 0.75, 0.95]:

| Bucket `x` | 5% | 25% | 50% | 75% | 95% |
|---|---|---|---|---|---|---|
| [0.00, 0.02) | -2.303 | -0.347 | 0 | 0.166 | 4.682 |
| [0.02, 0.08) | -1.854 | -1.192 | 0 | 0.005 | 3.365 |
| [0.08, 0.25) | -1.151 | -0.797 | 0 | 0.015 | 1.721 |
| [0.25, 1.00] | -2.648 | -1.409 | 0 | 0.206 | 1.721 |

Kuantil = `x + C * sd(h)`, dijepit ke [0, 1], dibulatkan 6 desimal, urut dinaikkan per baris.

## Hasil backtest

| Metrik | Ronde 1 | Ronde 2 |
|---|---|---|
| Pinball loss (practice) | 0.2752 | **0.2567** |
| Pinball loss (extra windows) | 1.79 | **1.49** |
| Cakupan interval 90% | 0.774 | **0.842** |
| Runtime | — | ~0.1 detik per case |

Deterministik (dua run menghasilkan byte identik) dan berjalan dengan
direktori input read-only.

## Lisensi

MIT — lihat `LICENSE`.
