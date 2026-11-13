# Peramal Harga "Next CEO of NVIDIA?" — make.fun

Entri untuk kompetisi `polymarket-nvidia-ceo-forecast-01`: meramal harga Yes
tiap market event Polymarket "Next CEO of NVIDIA?" pada 240 menit setelah
checkpoint, sebagai lima kuantil (5%, 25%, 50%, 75%, 95%) per menit.

## Cara jalan

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Membaca tiap `*.in` di direktori input dan menulis `<id>.out` yang sepadan.
Hanya pustaka standar Python; tanpa jaringan, tanpa keacakan — dua kali jalan
pada case yang sama menghasilkan byte yang sama.

## Model

- **Median**: harga terakhir, menyusut 0,02% per menit menuju nol (sekitar
  5% selama 4 jam). Tanpa ekstrapolasi tren — pada data latih, drift apa pun
  memperburuk pinball loss.
- **Sebaran**: proses Ornstein-Uhlenbeck, k = 0,012/menit:
  `var(h) = s^2 * (1 - exp(-2kh)) / (2k)`.
- **Skala inovasi s**: RMS perubahan 1-menit selama 360 menit terakhir,
  di-shrink 40% ke arah median lintas market (`0,6*s_sendiri + 0,4*median`),
  lantai 0,0003, lalu diskalakan menurut level harga
  (`0,3 + 0,7 * sqrt(max(x(1-x), 0,001)) / 0,5`).
- **Kuantil**: `median + z*sd`, z = (-1,644854; -0,67449; 0; 0,67449; 1,644854),
  dijepit ke [0, 1], dibulatkan 6 desimal, dijaga urut naik.

## Skor backtest (6 practice case kit)

- Model ini: **pinball loss ~0,275**
- Baseline house (persistensi + spread sqrt): **0,363589**

Jadi model ini mengalahkan baseline house dengan margin sekitar 24% pada
practice — dan harus mengalahkan baseline (atau model house) di final untuk
bisa masuk 100 tempat berhadiah.

## Lisensi

MIT — lihat `LICENSE`.
