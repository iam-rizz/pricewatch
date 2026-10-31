# Pricewatch digitalregistra

[![CI](https://github.com/iam-rizz/pricewatch/actions/workflows/ci.yml/badge.svg)](https://github.com/iam-rizz/pricewatch/actions/workflows/ci.yml)

Pricewatch mengambil harga reseller dari digitalregistra, lalu mencocokkannya dengan harga jual di
WHMCS Anda. Ada dua sumber harga: kolom Gold Slab di
[harga domain Indonesia](https://www.digitalregistra.co.id/harga-domain-indonesia/) dalam Rupiah, dan
[harga gTLD](https://www.digitalregistra.co.id/harga-gtld/) dalam USD. Kalau harga reseller berubah atau
harga jual di bawah rumus, Pricewatch mengirim pesan ke Telegram. Harga jual di atas rumus dianggap
disengaja dan tidak dilaporkan.

```
harga jual = ROUNDUP(reseller × (1 + PPN + margin), ke ribuan)
```

Rumus ini sama dengan Excel `=ROUNDUP(B7*(1+$C$2+$C$3),-3)`. PPN default 11% dan margin 3%,
keduanya bisa diubah lewat env. Harga di digitalregistra belum termasuk PPN.

Untuk gTLD, harga USD dikalikan kurs dulu, lalu harga jualnya dibulatkan ke atas ke kelipatan Rp500 (lihat
[Domain gTLD dan kurs](#domain-gtld-dan-kurs)).

Contoh hasil dengan harga Gold Slab per Oktober 2026:

| TLD | Reseller | Harga jual |
|---|---|---|
| .co.id | 270.000 | 308.000 |
| .id | 210.000 | 240.000 |
| .biz.id | 55.000 | 63.000 |
| .web.id / .or.id / .ac.id / .sch.id / .ponpes.id | 45.000 | 52.000 |
| .my.id | 22.000 | 26.000 |

Contoh gTLD dengan kurs 18.056 per USD (20 Oktober 2026):

| TLD | Aksi | Reseller | Harga jual |
|---|---|---|---|
| .com | register, renew, transfer | $11,75 | 242.000 |
| .net | register, renew, transfer | $11,93 | 246.000 |
| .xyz | register (promo reseller) | $1,91 | 39.500 |
| .xyz | renew, transfer | $14,90 | 307.000 |

## Daftar isi

- [Cara kerja](#cara-kerja)
  - [Harga promo](#harga-promo)
  - [Domain gTLD dan kurs](#domain-gtld-dan-kurs)
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
  - [WHMCS di belakang Cloudflare](#whmcs-di-belakang-cloudflare)
- [Tanpa Docker](#tanpa-docker)
- [Development](#development)

## Cara kerja

```
tiap INTERVAL_MINUTES (default 6 jam)
  │
  ├─ 1. Scrape tabel harga digitalregistra: domain .id (Gold Slab, Rupiah) dan gTLD (USD)
  ├─ 2. Ambil kurs USD ke IDR dari open.er-api.com
  ├─ 3. Ambil harga jual 1 tahun dari WHMCS API (GetTLDPricing)
  ├─ 4. Hitung harga jual seharusnya per TLD per aksi (register / renew / transfer)
  ├─ 5. Bandingkan dengan state run sebelumnya (volume /data/state.json)
  └─ 6. Kirim Telegram hanya kalau ada yang berubah
```

Domain .id yang dicek adalah semua TLD di tabel Gold Slab. Dari 400 gTLD di tabel digitalregistra,
yang dicek hanya yang Anda jual di WHMCS. TLD WHMCS yang tidak ada di kedua tabel, misalnya .ai.id,
dilewati.

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
promonya tidak memicu notifikasi. Begitu harganya kembali sesuai rumus atau di atasnya, Pricewatch mengirim
pengingat sekali untuk menghapusnya dari `PROMO`. Aksi lain di TLD yang sama, misalnya renew .my.id, tetap dicek seperti biasa.

### Domain gTLD dan kurs

Harga gTLD di digitalregistra dalam USD. Pricewatch menghitungnya seperti ini:

```
kurs        = kurs live, dibulatkan ke atas ke rupiah
harga jual  = ROUNDUP(USD × kurs × (1 + PPN + margin), ke kelipatan Rp500)
modal       = USD × kurs live × (1 + PPN)
```

Kurs live diambil dari [open.er-api.com](https://open.er-api.com), yang diperbarui sekali sehari. Karena
kurs bergerak setiap hari, harga seharusnya ikut bergeser. Pembulatan harga jual ke Rp500 menahan
sebagian besar pergeseran kecil, tapi harga yang dekat batas kelipatan akan sesekali berpindah. Modal
dihitung dengan kurs live, jadi status RUGI hanya muncul kalau Anda memang rugi dengan kurs hari itu.

Perubahan kurs saja tidak memicu notifikasi. Pesan baru dikirim kalau status harga berubah, misalnya
harga yang tadinya sesuai menjadi 🟡 karena kurs naik. Kurs yang dipakai selalu ditampilkan di baris 💱,
termasuk kurs sebelumnya kalau berubah.

Kalau harga seharusnya terlalu sering bergeser, bulatkan kurs ke kelipatan yang lebih besar dengan
`USD_RATE_ROUND_TO`, misalnya `100`. Kurs lalu dibulatkan ke atas ke kelipatan itu dan baru turun setelah
kurs live turun satu kelipatan ditambah seperlimanya. Dengan `100`, kurs 18.200 baru turun ke 18.100
setelah kurs live mencapai 18.080 atau lebih rendah. Harga jual jadi sedikit lebih tinggi, paling banyak
sekitar 0,5% untuk kelipatan Rp100.

Kalau halaman gTLD atau layanan kurs gagal diakses, domain .id tetap dicek seperti biasa dan Pricewatch
mengirim 🚨 khusus gTLD sekali.

Register gTLD yang sedang promo di digitalregistra (harga normal dicoret, diikuti harga promo) dihitung
dari harga promonya. Saat promo reseller mulai atau selesai, harga USD-nya berubah dan Pricewatch
mengirim 📢. Kalau Anda sengaja menjual di bawah rumus, daftarkan di `PROMO` seperti domain .id.

Harga di tabel gTLD tidak selalu sama dengan halaman promo bulanan digitalregistra. Pada Oktober 2026,
207 dari 211 harga promo sama, tapi register .asia tercatat $1,88 di tabel dan $1,32 di halaman promo.
Pricewatch memakai tabel gTLD. Menurut digitalregistra, harga paling akurat ada di panel reseller
(*Configuration → Products*), jadi cek di sana kalau ada harga yang meragukan.

Pengecekan gTLD bisa dimatikan dengan `GTLD_ENABLED=false`.

## Notifikasi

| Ikon | Kejadian |
|---|---|
| 📢 | Harga reseller naik atau turun, ada TLD baru, atau TLD hilang dari tabel |
| 🔴 RUGI | Harga jual di bawah modal (reseller + PPN) |
| 🟡 | Harga jual di bawah hasil rumus, tapi masih di atas modal. Harga di atas rumus tidak dilaporkan |
| ⚪ | TLD atau aksi (register, renew, transfer) tidak dijual di WHMCS |
| 🏷️ | Item di `PROMO` yang dijual di bawah harga rumus. Hanya ditampilkan, tidak memicu notifikasi sendiri |
| ℹ️ | Item di `PROMO` yang harganya sudah kembali sesuai rumus atau di atasnya. Dikirim sekali sebagai pengingat untuk menghapusnya dari `PROMO` |
| 💱 | Kurs USD ke IDR yang dipakai untuk gTLD, termasuk kurs sebelumnya kalau berubah. Muncul di pesan yang memuat gTLD, bukan pemicu notifikasi sendiri |
| ✅ | Semua harga sesuai atau di atas rumus. Dikirim saat run pertama dan saat masalah sebelumnya sudah beres |
| 🚨 | Pengambilan data gagal, misalnya struktur tabel digitalregistra berubah, open.er-api.com tidak bisa dihubungi, atau kredensial WHMCS salah |

Register, renew, dan transfer dengan status dan harga yang sama ditulis dalam satu baris. Pesan yang
lebih dari 4.096 karakter (batas Telegram) dipecah menjadi beberapa pesan per baris.

Contoh pesan:

```
📢 Harga reseller digitalregistra (Gold Slab) berubah
🔺 .web.id register: Rp45.000 → Rp47.000

📢 Harga reseller gTLD digitalregistra berubah
🔺 .com register: $11.75 → $12.10

⚠️ Harga jual WHMCS perlu dicek (4)
🔴 RUGI .com register: jual Rp240.500 < modal Rp242.498 → seharusnya Rp249.500
🔴 RUGI .my.id register: jual Rp24.000 < modal Rp24.420 → seharusnya Rp26.000
🔴 RUGI .web.id register: jual Rp52.000 < modal Rp52.170 → seharusnya Rp54.000
🟡 .com renew, transfer: jual Rp240.500, seharusnya Rp242.000

💱 Kurs gTLD Rp18.056 per USD (kurs live dibulatkan ke atas ke rupiah)
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
mata uangnya bukan IDR (atur `WHMCS_CURRENCY_ID`). gTLD yang Anda jual muncul di output yang sama,
diikuti baris 💱 berisi kurs yang dipakai.

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
2026-10-20 02:04:59 WIB INFO Cek selesai: 26 TLD, 2 masalah, 2 promo, notifikasi dikirim
2026-10-20 02:04:59 WIB INFO Cek berikutnya sekitar 02:14:59 WIB
```

Jumlah TLD adalah domain .id ditambah gTLD yang Anda jual. Kalau baris `Cek selesai` tidak muncul lagi
setelah jam yang tertulis di `Cek berikutnya`, berarti loop-nya macet. Log dibatasi tiga file masing-masing
5 MB. Kalau satu pengecekan gagal, misalnya karena Telegram sedang down, container tetap jalan dan mencoba
lagi di jadwal berikutnya.

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
| `GTLD_ENABLED` | | `true` | Cek harga gTLD. Isi `false` untuk hanya mengecek domain .id |
| `GTLD_ROUND_TO` | | `500` | Harga jual gTLD dibulatkan ke atas ke kelipatan ini (Rupiah) |
| `USD_RATE_ROUND_TO` | | `1` | Kurs live dibulatkan ke atas ke kelipatan ini sebelum dipakai. `1` berarti mengikuti kurs live. Isi `100` atau lebih kalau harga seharusnya terlalu sering bergeser |
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
| 🚨 `WhmcsError: HTTP 502 ... (bukan JSON WHMCS)` atau `Connection reset by peer` | WHMCS di belakang Cloudflare dan request API diputus. Arahkan container langsung ke IP origin, lihat [WHMCS di belakang Cloudflare](#whmcs-di-belakang-cloudflare). Kalau tetap di-reset, whitelist IP server di WAF hosting (ModSecurity/Imunify360) dan hapus IP dari *Banned IPs* WHMCS |
| 🚨 `ScrapeError: ...` | Struktur halaman digitalregistra berubah. Parser di `pricewatch/registra.py` (domain .id) atau `pricewatch/gtld.py` (gTLD) perlu disesuaikan |
| 🚨 *Pengecekan harga gTLD gagal* dengan `KursError` atau error koneksi ke open.er-api.com | Layanan kurs sedang bermasalah. Domain .id tetap dicek seperti biasa, dan gTLD dicoba lagi di jadwal berikutnya. Kalau berlangsung lama, matikan sementara dengan `GTLD_ENABLED=false` |
| `--test-telegram` error `chat not found` | `TELEGRAM_CHAT_ID` salah, bot belum pernah di-chat, atau bot belum masuk grup |
| `401 Unauthorized` dari Telegram | `TELEGRAM_BOT_TOKEN` salah |
| `TelegramError: ... message thread not found` | `TELEGRAM_THREAD_ID` salah. Bisa jadi yang tersalin ID pesan, bukan ID topik |
| `TelegramError: ... not enough rights` | Topik dikunci, jadikan bot admin grup |
| Semua TLD ⚪ | TLD belum ada di WHMCS, atau mata uang salah (`WHMCS_CURRENCY_ID`) |
| Tidak ada notif sama sekali | Wajar kalau tidak ada perubahan. Cek `docker compose logs` untuk memastikan |
| Harga gTLD di pesan berbeda dengan halaman promo digitalregistra | Pricewatch memakai tabel harga gTLD, yang kadang berbeda dengan halaman promo. Cek harga di panel reseller. Lihat [Domain gTLD dan kurs](#domain-gtld-dan-kurs) |
| Hampir semua gTLD 🟡 dengan selisih kecil | Harga WHMCS dihitung dengan kurs lama. Sesuaikan harga di WHMCS, atau bulatkan kurs dengan `USD_RATE_ROUND_TO` |
| `docker compose pull` ditolak (denied) | Package GHCR masih private. Ubah jadi public di GitHub, atau build sendiri dengan `--build` |

### WHMCS di belakang Cloudflare

Kalau WHMCS memakai Cloudflare, request API dari server bisa diblokir atau dibalas 502. Pricewatch bisa
menghubungi IP origin langsung tanpa lewat Cloudflare. Salin contoh override, lalu isi host dan IP origin:

```bash
cp compose.override.example.yaml compose.override.yaml
nano compose.override.yaml   # contoh: "billing.domainanda.com:203.0.113.10"
docker compose up -d
```

`compose.override.yaml` tidak masuk git, jadi IP origin tidak ikut ter-commit. Untuk cek, jalankan
`docker compose exec pricewatch getent hosts billing.domainanda.com` dan pastikan IP yang muncul adalah
IP origin. Sertifikat HTTPS di origin harus valid untuk nama domainnya (misalnya Let's Encrypt), bukan
Cloudflare Origin Certificate, karena sertifikat itu tidak dipercaya di luar Cloudflare.

Jangan mengetes endpoint API tanpa kredensial. WHMCS mencatatnya sebagai login gagal dan bisa memblokir
IP server setelah beberapa kali percobaan.

## Tanpa Docker

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && chmod 600 .env   # isi, dan aktifkan STATE_FILE=state.json
./run.sh --test-telegram
./run.sh --dry-run
```

Tanpa Docker, zona waktu log tetap dibaca dari `TZ` (default `Asia/Jakarta`).

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
├── registra.py   # scraper tabel domain .id digitalregistra (Gold Slab)
├── gtld.py       # scraper tabel gTLD digitalregistra (USD)
├── kurs.py       # kurs USD ke IDR dari open.er-api.com
├── whmcs.py      # client WHMCS GetTLDPricing
├── check.py      # deteksi rugi / mismatch / missing / perubahan harga
├── telegram.py   # kirim pesan
└── main.py       # state, format pesan, CLI, loop
```

Riwayat perubahan ada di [CHANGELOG.md](CHANGELOG.md).

GitHub Actions menjalankan tes di setiap push dan pull request. Push ke `main` yang lolos tes
mem-publish image `ghcr.io/iam-rizz/pricewatch:latest`, dan tag `v*` mem-publish image dengan tag versi.

## Lisensi

[MIT](LICENSE)
