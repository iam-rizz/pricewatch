# Pricewatch digitalregistra

[![CI](https://github.com/iam-rizz/pricewatch/actions/workflows/ci.yml/badge.svg)](https://github.com/iam-rizz/pricewatch/actions/workflows/ci.yml)

Pricewatch mengambil harga reseller domain Indonesia dari kolom Gold Slab di
[digitalregistra](https://www.digitalregistra.co.id/harga-domain-indonesia/), lalu mencocokkannya
dengan harga jual di WHMCS Anda. Kalau harga reseller berubah atau harga jual tidak sesuai rumus,
Pricewatch mengirim pesan ke Telegram.

```
harga jual = ROUNDUP(reseller × (1 + PPN + margin), ke ribuan)
```

Rumus ini sama dengan Excel `=ROUNDUP(B7*(1+$C$2+$C$3),-3)`. PPN default 11% dan margin 3%,
keduanya bisa diubah lewat env. Harga di digitalregistra belum termasuk PPN.

Contoh hasil dengan harga Gold Slab per Oktober 2026:

| TLD | Reseller | Harga jual |
|---|---|---|
| .co.id | 270.000 | 308.000 |
| .id | 210.000 | 240.000 |
| .biz.id | 55.000 | 63.000 |
| .web.id / .or.id / .ac.id / .sch.id / .ponpes.id | 45.000 | 52.000 |
| .my.id | 22.000 | 26.000 |

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

Pricewatch hanya mengecek TLD yang ada di tabel digitalregistra. TLD lain di WHMCS, misalnya .com
atau .ai.id, dilewati.

Hitungannya memakai `Decimal` supaya pembulatan ke atas sama persis dengan Excel. Dengan float,
`1 + 0.11 + 0.03` bernilai `1.1400000000000001`, sehingga reseller 200.000 dihitung `228000.00000000003`
dan dibulatkan ke 229.000, padahal seharusnya 228.000.

Masalah yang sama hanya dikirim sekali. Pesan berikutnya baru dikirim kalau kondisinya berubah.

### Harga promo

Harga promo yang sengaja dipasang di bawah modal akan terus dilaporkan sebagai RUGI. Untuk mencegahnya,
daftarkan item promo di `PROMO` dengan format `tld:aksi`, dipisah koma:

```env
PROMO=my.id:register,biz.id:register
```

Selama harga jualnya di bawah harga rumus, item itu masuk ke bagian 🏷️ Promo dan perubahan harga
promonya tidak memicu notifikasi. Begitu harganya kembali sesuai rumus, Pricewatch mengirim pengingat
sekali untuk menghapusnya dari `PROMO`. Kalau harganya malah di atas rumus, item itu tetap dilaporkan
sebagai 🟡. Aksi lain di TLD yang sama, misalnya renew .my.id, tetap dicek seperti biasa.

## Notifikasi

| Ikon | Kejadian |
|---|---|
| 📢 | Harga reseller naik atau turun, ada TLD baru, atau TLD hilang dari tabel |
| 🔴 RUGI | Harga jual di bawah modal (reseller + PPN) |
| 🟡 | Harga jual tidak sama dengan hasil rumus |
| ⚪ | TLD atau aksi (register, renew, transfer) tidak dijual di WHMCS |
| 🏷️ | Item di `PROMO` yang dijual di bawah harga rumus. Hanya ditampilkan, tidak memicu notifikasi sendiri |
| ℹ️ | Item di `PROMO` yang harganya sudah kembali sesuai rumus. Dikirim sekali sebagai pengingat untuk menghapusnya dari `PROMO` |
| ✅ | Semua harga sesuai. Dikirim saat run pertama dan saat masalah sebelumnya sudah beres |
| 🚨 | Pengambilan data gagal, misalnya struktur tabel digitalregistra berubah atau kredensial WHMCS salah |

Contoh pesan:

```
📢 Harga reseller digitalregistra (Gold Slab) berubah
🔺 .web.id register: Rp45.000 → Rp47.000

⚠️ Harga jual WHMCS perlu dicek (2)
🔴 RUGI .my.id register: jual Rp24.000 < modal Rp24.420 → seharusnya Rp26.000
🟡 .web.id register: jual Rp52.000, seharusnya Rp54.000
```

## Panduan deploy

Anda butuh server Linux dengan Docker dan Docker Compose v2, akses admin WHMCS, dan akun Telegram.

### 1. Siapkan API WHMCS

1. Login ke admin WHMCS.
2. Buka *Configuration (⚙) → System Settings → Manage API Credentials*. Di versi lama menunya
   *Setup → Staff Management → Manage API Credentials*.
3. Di tab *API Roles*, klik *Create API Role*. Beri nama, misalnya `pricewatch`, centang `GetTLDPricing`
   saja (kategori *Domains*), lalu simpan.
4. Di tab *API Credentials*, klik *Generate New API Credential*. Pilih admin user dan role `pricewatch`.
   Catat identifier dan secret-nya. Secret hanya ditampilkan sekali.
5. Buka *Configuration → System Settings → General Settings → Security → API IP Access Restriction*
   dan tambahkan IP publik server yang akan menjalankan Pricewatch. Kalau server punya IPv4 dan IPv6,
   tambahkan keduanya. Cek dari server tersebut dengan `curl -4 ifconfig.me` dan `curl -6 ifconfig.me`.

URL API WHMCS adalah URL instalasi WHMCS ditambah `/includes/api.php`. Contoh:
`https://billing.domainanda.com/includes/api.php`.

### 2. Siapkan bot Telegram

1. Kirim `/newbot` ke @BotFather, ikuti instruksinya, dan catat token bot yang diberikan.
2. Untuk notifikasi ke chat pribadi, kirim pesan apa saja ke bot Anda. Untuk notifikasi ke grup,
   tambahkan bot ke grup lalu kirim pesan di grup, misalnya `/start@nama_bot`.
3. Ambil `chat_id`:
   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates"
   ```
   Cari `"chat":{"id": ...}`. Chat ID grup biasanya negatif, misalnya `-1001234567890`.

#### Grup forum (topik)

Tanpa `TELEGRAM_THREAD_ID`, pesan di grup forum masuk ke topik *General*. Untuk mengirim ke topik lain,
ambil link topiknya: di aplikasi Telegram, klik kanan nama topik lalu pilih *Copy Link*.

```
https://t.me/c/3658699335/215082
              └────┬────┘ └──┬──┘
            chat (tambahkan   ID topik
            prefix -100)
```

```env
TELEGRAM_CHAT_ID=-1003658699335
TELEGRAM_THREAD_ID=215082
```

Link pesan di dalam topik bentuknya `t.me/c/<chat>/<topik>/<pesan>`. Dari link seperti itu, pakai
angka yang di tengah. Link pesan di luar topik juga hanya berisi satu angka setelah chat, jadi kalau
ragu, ambil ulang link dari nama topiknya. Bot harus menjadi anggota grup. Kalau topiknya dikunci,
bot harus admin.

### 3. Siapkan server

Kalau Docker belum terpasang:

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

Variabel lainnya dijelaskan di bagian [Konfigurasi](#konfigurasi).

### 5. Uji coba

```bash
# Tes bot Telegram → harus masuk pesan "🔔 Tes notifikasi ..."
docker compose run --rm pricewatch --test-telegram

# Preview hasil pengecekan di terminal tanpa kirim Telegram
docker compose run --rm pricewatch --dry-run
```

Kalau output dry-run berisi 🚨, kredensial atau whitelist IP WHMCS belum benar; lihat
[Troubleshooting](#troubleshooting). Kalau semua TLD bertanda ⚪, TLD-nya belum dibuat di WHMCS atau
mata uangnya bukan IDR (atur `WHMCS_CURRENCY_ID`).

Dry-run juga menyimpan state. Kalau state itu dibiarkan, ringkasan pertama tidak akan dikirim ke
Telegram, jadi hapus dulu sebelum menjalankan Pricewatch untuk pertama kali:
```bash
docker compose down -v
```

### 6. Jalankan

```bash
docker compose up -d
docker compose logs -f
```

Image diambil dari `ghcr.io/iam-rizz/pricewatch:latest`. Kalau mau build sendiri dari source:

```bash
docker compose up -d --build
```

Ringkasan pertama (✅ atau ⚠️) masuk ke Telegram beberapa detik setelah container jalan. Karena
`restart: unless-stopped`, container ikut jalan lagi setelah server reboot.

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

Setiap pengecekan menulis satu baris ringkasan, dan mode loop mencatat jam pengecekan berikutnya:

```
2026-10-20 02:04:59 WIB INFO Cek selesai: 9 TLD, 2 masalah, 2 promo, notifikasi dikirim
2026-10-20 02:04:59 WIB INFO Cek berikutnya sekitar 02:14:59 WIB
```

Kalau baris `Cek selesai` tidak muncul lagi setelah jam yang tertulis di `Cek berikutnya`, berarti
loop-nya macet. Log dibatasi tiga file masing-masing 5 MB. Kalau satu pengecekan gagal, misalnya karena Telegram
sedang down, container tetap jalan dan mencoba lagi di jadwal berikutnya.

## Konfigurasi

| Variabel | Wajib | Default | Keterangan |
|---|---|---|---|
| `WHMCS_API_URL` | ✅ | | URL `.../includes/api.php` |
| `WHMCS_IDENTIFIER` | ✅ | | API identifier |
| `WHMCS_SECRET` | ✅ | | API secret |
| `WHMCS_CURRENCY_ID` | | mata uang default WHMCS | ID mata uang (IDR) kalau WHMCS punya banyak mata uang |
| `TELEGRAM_BOT_TOKEN` | ✅ | | Token dari @BotFather |
| `TELEGRAM_CHAT_ID` | ✅ | | Chat ID pribadi atau grup |
| `TELEGRAM_THREAD_ID` | | | ID topik di grup forum. Kosongkan untuk chat biasa atau topik General |
| `PPN_PERCENT` | | `11` | PPN dalam persen |
| `MARGIN_PERCENT` | | `3` | Margin dalam persen |
| `PROMO` | | | Item promo yang tidak dihitung sebagai masalah, misalnya `my.id:register,biz.id:register`. Lihat [Harga promo](#harga-promo) |
| `TZ` | | `Asia/Jakarta` | Zona waktu jam di log, dengan nama IANA seperti `Asia/Makassar` atau `UTC` |
| `INTERVAL_MINUTES` | | `360` | Jarak antar-pengecekan dalam menit, untuk mode `--loop` dan Docker |
| `STATE_FILE` | | `/data/state.json` di Docker | Hanya dipakai saat jalan tanpa Docker |

Opsi CLI:

| Opsi | Fungsi |
|---|---|
| *(tanpa opsi)* | Cek sekali lalu keluar |
| `--loop` | Cek terus tiap `INTERVAL_MINUTES` (default di Docker) |
| `--dry-run` | Cetak pesan ke terminal tanpa mengirim ke Telegram |
| `--test-telegram` | Kirim pesan tes lalu keluar |

## Troubleshooting

| Gejala | Penyebab dan solusi |
|---|---|
| 🚨 `WhmcsError: Invalid IP x.x.x.x` | Tambahkan IP tersebut di *API IP Access Restriction* WHMCS |
| 🚨 `WhmcsError: Invalid or missing credentials` atau `Authentication Failed` | Identifier atau secret salah, atau credential sudah dihapus. Periksa juga apakah ada spasi atau tanda kutip yang ikut tersalin ke `.env` |
| 🚨 `WhmcsError: ... permission` | Role API belum mencentang `GetTLDPricing` |
| 🚨 `WhmcsError: HTTP 404 ... (bukan JSON WHMCS)` | `WHMCS_API_URL` salah. Alamatnya harus diakhiri `/includes/api.php` |
| 🚨 `WhmcsError: HTTP 403 ... (bukan JSON WHMCS)` | Request diblokir sebelum sampai ke WHMCS, biasanya oleh firewall atau WAF |
| 🚨 `ScrapeError: ...` | Struktur halaman digitalregistra berubah. Parser di `pricewatch/registra.py` perlu disesuaikan |
| `--test-telegram` error `chat not found` | `TELEGRAM_CHAT_ID` salah, bot belum pernah di-chat, atau bot belum masuk grup |
| `401 Unauthorized` dari Telegram | `TELEGRAM_BOT_TOKEN` salah |
| `TelegramError: ... message thread not found` | `TELEGRAM_THREAD_ID` salah. Bisa jadi yang tersalin ID pesan, bukan ID topik |
| `TelegramError: ... not enough rights` | Topik dikunci, jadikan bot admin grup |
| Semua TLD ⚪ | TLD belum ada di WHMCS, atau mata uang salah (`WHMCS_CURRENCY_ID`) |
| Tidak ada notif sama sekali | Wajar kalau tidak ada perubahan. Cek `docker compose logs` untuk memastikan |
| `docker compose pull` ditolak (denied) | Package GHCR masih private. Ubah jadi public di GitHub, atau build sendiri dengan `--build` |

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

Isi folder `pricewatch/`:

```
pricewatch/
├── pricing.py    # rumus harga jual & modal
├── registra.py   # scraper tabel digitalregistra (Gold Slab)
├── whmcs.py      # client WHMCS GetTLDPricing
├── check.py      # deteksi rugi / mismatch / missing / perubahan harga
├── telegram.py   # kirim pesan
└── main.py       # state, format pesan, CLI, loop
```

GitHub Actions menjalankan tes di setiap push dan pull request. Push ke `main` yang lolos tes
mem-publish image `ghcr.io/iam-rizz/pricewatch:latest`, dan tag `v*` mem-publish image dengan tag versi.

## Lisensi

[MIT](LICENSE)
