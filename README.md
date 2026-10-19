# Pricewatch digitalregistra

[![CI](https://github.com/iam-rizz/pricewatch/actions/workflows/ci.yml/badge.svg)](https://github.com/iam-rizz/pricewatch/actions/workflows/ci.yml)

Memantau harga reseller domain Indonesia di
[digitalregistra](https://www.digitalregistra.co.id/harga-domain-indonesia/) (kolom **Gold Slab**)
dan membandingkannya dengan harga jual di **WHMCS** Anda. Notifikasi dikirim ke **Telegram**
kalau harga reseller berubah atau harga jual tidak sesuai rumus.

```
harga jual = ROUNDUP(reseller × (1 + PPN + margin), ke ribuan)
```

Rumus ini sama dengan Excel `=ROUNDUP(B7*(1+$C$2+$C$3),-3)`. Default-nya PPN 11% dan margin 3%,
dan keduanya bisa diubah lewat env. Harga digitalregistra dianggap **belum termasuk PPN**.

Contoh hasil (Gold Slab):

| TLD | Reseller | Harga jual |
|---|---|---|
| .co.id | 270.000 | 308.000 |
| .id | 210.000 | 240.000 |
| .biz.id | 55.000 | 63.000 |
| .web.id / .or.id / .ac.id / .sch.id / .ponpes.id | 45.000 | 52.000 |
| .my.id | 22.000 | 26.000 |

---

## Daftar isi

- [Cara kerja](#cara-kerja)
- [Notifikasi](#notifikasi)
- [Panduan deploy](#panduan-deploy)
  - [1. Siapkan API WHMCS](#1-siapkan-api-whmcs)
  - [2. Siapkan bot Telegram](#2-siapkan-bot-telegram)
  - [3. Siapkan server](#3-siapkan-server)
  - [4. Konfigurasi `.env`](#4-konfigurasi-env)
  - [5. Uji coba](#5-uji-coba)
  - [6. Jalankan](#6-jalankan)
- [Operasional](#operasional)
- [Konfigurasi](#konfigurasi)
- [Troubleshooting](#troubleshooting)
- [Tanpa Docker](#tanpa-docker)
- [Development](#development)

---

## Cara kerja

```
tiap INTERVAL_MINUTES (default 6 jam)
  │
  ├─ 1. Scrape tabel harga digitalregistra → kolom Gold Slab (register / renew / transfer)
  ├─ 2. Ambil harga jual 1 tahun dari WHMCS API (GetTLDPricing)
  ├─ 3. Hitung harga jual seharusnya per TLD per aksi
  ├─ 4. Bandingkan dengan state run sebelumnya (volume /data/state.json)
  └─ 5. Kirim Telegram hanya kalau ada yang berubah
```

- Yang dicek hanya TLD yang ada di tabel digitalregistra (domain Indonesia). TLD lain di WHMCS diabaikan.
- Perhitungan memakai `Decimal`, bukan float, jadi hasil pembulatannya sama persis dengan Excel.
- Masalah yang sama **tidak dikirim berulang**. Notif baru dikirim lagi setelah kondisinya berubah.

## Notifikasi

| Ikon | Kejadian |
|---|---|
| 📢 | Harga reseller naik / turun / TLD baru / hilang dari tabel |
| 🔴 **RUGI** | Harga jual di bawah modal (reseller + PPN) |
| 🟡 | Harga jual tidak sama dengan hasil rumus |
| ⚪ | TLD / aksi tidak dijual di WHMCS |
| ✅ | Semua harga sudah sesuai (dikirim saat run pertama dan saat masalah sudah beres) |
| 🚨 | Scraper / API gagal, misalnya struktur tabel digitalregistra berubah atau kredensial WHMCS salah |

Contoh:

```
📢 Harga reseller digitalregistra (Gold Slab) berubah
🔺 .web.id register: Rp45.000 → Rp47.000

⚠️ Harga jual WHMCS perlu dicek (2)
🔴 RUGI .my.id register: jual Rp24.000 < modal Rp24.420 → seharusnya Rp26.000
🟡 .web.id register: jual Rp52.000, seharusnya Rp54.000
```

---

## Panduan deploy

Yang dibutuhkan:

- Server Linux (VPS) dengan **Docker** dan **Docker Compose v2**
- Akses admin WHMCS
- Akun Telegram

### 1. Siapkan API WHMCS

1. Login ke admin WHMCS.
2. Buka **Configuration (⚙) → System Settings → Manage API Credentials**
   (di versi lama: *Setup → Staff Management → Manage API Credentials*).
3. Tab **API Roles** → **Create API Role**. Beri nama misalnya `pricewatch`, lalu centang **hanya**
   `GetTLDPricing` (kategori *Domains*). Simpan.
4. Tab **API Credentials** → **Generate New API Credential**. Pilih admin user dan role `pricewatch`.
   Catat **Identifier** dan **Secret**, karena secret hanya tampil sekali.
5. Buka **Configuration → System Settings → General Settings → Security → API IP Access Restriction**,
   lalu tambahkan **IP publik server** yang akan menjalankan Pricewatch. Cek IP-nya dengan
   `curl -4 ifconfig.me` dari server tersebut.

URL API WHMCS adalah URL instalasi WHMCS ditambah `/includes/api.php`. Contoh:
`https://billing.domainanda.com/includes/api.php`.

### 2. Siapkan bot Telegram

1. Chat **@BotFather** → `/newbot` → ikuti instruksi → catat **token bot**.
2. Tentukan tujuan notifikasi:
   - **Chat pribadi:** kirim pesan apa saja ke bot Anda.
   - **Grup:** tambahkan bot ke grup, lalu kirim pesan di grup (misalnya `/start@nama_bot`).
3. Ambil `chat_id`:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   Cari `"chat":{"id": ...}`. Chat ID grup biasanya negatif, misalnya `-1001234567890`.

### 3. Siapkan server

Install Docker (kalau belum ada):

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # logout-login setelah ini
docker compose version          # pastikan Compose v2
```

Ambil kode:

```bash
git clone https://github.com/iam-rizz/pricewatch.git
cd pricewatch
```

### 4. Konfigurasi `.env`

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Isi minimal:

```env
WHMCS_API_URL=https://billing.domainanda.com/includes/api.php
WHMCS_IDENTIFIER=xxxxxxxx
WHMCS_SECRET=xxxxxxxx
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_CHAT_ID=-1001234567890
```

Penjelasan semua variabel ada di bagian [Konfigurasi](#konfigurasi).

### 5. Uji coba

```bash
# Tes bot Telegram → harus masuk pesan "🔔 Tes notifikasi ..."
docker compose run --rm pricewatch --test-telegram

# Preview hasil pengecekan di terminal tanpa kirim Telegram
docker compose run --rm pricewatch --dry-run
```

Periksa output dry-run:

- Ada 🚨 berarti kredensial atau whitelist IP WHMCS belum benar. Lihat [Troubleshooting](#troubleshooting).
- Semua TLD ⚪ berarti TLD belum dibuat di WHMCS, atau mata uangnya bukan IDR (atur `WHMCS_CURRENCY_ID`).

> **Penting:** dry-run tetap menyimpan state. Supaya ringkasan pertama tetap terkirim ke Telegram,
> reset state sebelum menjalankan untuk pertama kali:
> ```bash
> docker compose down -v
> ```

### 6. Jalankan

```bash
docker compose up -d
docker compose logs -f
```

Image diambil dari `ghcr.io/iam-rizz/pricewatch:latest`. Kalau mau build sendiri dari source:

```bash
docker compose up -d --build
```

Setelah container jalan, ringkasan pertama (✅ atau ⚠️) akan masuk ke Telegram dalam beberapa detik.
Container otomatis jalan lagi saat server reboot (`restart: unless-stopped`).

---

## Operasional

| Tugas | Perintah |
|---|---|
| Lihat log | `docker compose logs -f` |
| Status | `docker compose ps` |
| Cek sekarang (tanpa menunggu jadwal) | `docker compose restart` |
| Update ke versi terbaru | `git pull && docker compose pull && docker compose up -d` |
| Update dari source | `git pull && docker compose up -d --build` |
| Lihat state | `docker compose exec pricewatch cat /data/state.json` |
| Reset state (notif ulang dari awal) | `docker compose down -v && docker compose up -d` |
| Stop | `docker compose down` |

Ukuran log dibatasi 5 MB × 3 file. Kalau satu pengecekan gagal (misalnya Telegram down),
container tetap hidup dan mencoba lagi di jadwal berikutnya.

## Konfigurasi

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `WHMCS_API_URL` | ✅ | | URL `.../includes/api.php` |
| `WHMCS_IDENTIFIER` | ✅ | | API identifier |
| `WHMCS_SECRET` | ✅ | | API secret |
| `WHMCS_CURRENCY_ID` | | mata uang default WHMCS | ID mata uang (IDR) kalau WHMCS punya banyak mata uang |
| `TELEGRAM_BOT_TOKEN` | ✅ | | Token dari @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | | Chat ID pribadi / grup |
| `PPN_PERCENT` | | `11` | PPN dalam persen |
| `MARGIN_PERCENT` | | `3` | Margin dalam persen |
| `INTERVAL_MINUTES` | | `360` | Interval pengecekan (mode `--loop` / Docker) |
| `STATE_FILE` | | `/data/state.json` di Docker | Hanya untuk run tanpa Docker |

Opsi CLI:

| Opsi | Fungsi |
|---|---|
| *(tanpa opsi)* | Cek sekali lalu keluar |
| `--loop` | Cek terus tiap `INTERVAL_MINUTES` (default di Docker) |
| `--dry-run` | Cetak pesan ke terminal, tidak kirim Telegram |
| `--test-telegram` | Kirim pesan tes lalu keluar |

## Troubleshooting

| Gejala | Penyebab / solusi |
|---|---|
| 🚨 `WhmcsError: Invalid IP x.x.x.x` | Tambahkan IP tersebut di *API IP Access Restriction* WHMCS |
| 🚨 `WhmcsError: Authentication Failed` | Identifier atau secret salah, atau credential sudah dihapus |
| 🚨 `WhmcsError: ... permission` | Role API belum mencentang `GetTLDPricing` |
| 🚨 `HTTPError: 404` ke WHMCS | `WHMCS_API_URL` salah, pastikan diakhiri `/includes/api.php` |
| 🚨 `ScrapeError: ...` | Struktur halaman digitalregistra berubah, perlu update parser di `pricewatch/registra.py` |
| `--test-telegram` error `400 chat not found` | `TELEGRAM_CHAT_ID` salah, atau bot belum pernah di-chat / belum masuk grup |
| `401 Unauthorized` dari Telegram | `TELEGRAM_BOT_TOKEN` salah |
| Semua TLD ⚪ | TLD belum ada di WHMCS, atau mata uang salah (`WHMCS_CURRENCY_ID`) |
| Tidak ada notif sama sekali | Normal kalau tidak ada perubahan. Cek `docker compose logs` |
| `docker compose pull` ditolak (denied) | Package GHCR masih private. Buat jadi public di GitHub, atau pakai `--build` |

## Tanpa Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && chmod 600 .env   # isi, dan aktifkan STATE_FILE=state.json
./run.sh --test-telegram
./run.sh --dry-run
```

Cron (tiap 6 jam):

```
0 */6 * * * /path/ke/pricewatch/run.sh >> /path/ke/pricewatch/pricewatch.log 2>&1
```

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Struktur:

```
pricewatch/
├── pricing.py    # rumus harga jual & modal
├── registra.py   # scraper tabel digitalregistra (Gold Slab)
├── whmcs.py      # client WHMCS GetTLDPricing
├── check.py      # deteksi rugi / mismatch / missing / perubahan harga
├── telegram.py   # kirim pesan
└── main.py       # state, format pesan, CLI, loop
```

Setiap push ke `main` menjalankan tes. Kalau tes lulus, image di-publish ke
`ghcr.io/iam-rizz/pricewatch:latest`. Tag `v*` juga menghasilkan image dengan tag versi.

## Lisensi

[MIT](LICENSE)
