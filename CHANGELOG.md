# Changelog

Semua perubahan dirilis pada 20 Oktober 2026. Nomor dalam kurung adalah pull request di GitHub.

## Belum dirilis

- Harga jual di atas rumus tidak lagi dilaporkan sebagai 🟡. Yang dilaporkan hanya harga di bawah rumus
  (🟡) atau di bawah modal (🔴 RUGI). Item `PROMO` yang harganya di atas rumus dianggap promonya sudah
  selesai (ℹ️).
- Request ke API WHMCS memakai User-Agent Pricewatch, bukan `python-requests`. Sebagian hosting memutus
  koneksi dari User-Agent `python-requests` tanpa log, dan lewat Cloudflare terlihat sebagai HTTP 502.

## Domain gTLD

- Kurs gTLD mengikuti kurs live secara default (`USD_RATE_ROUND_TO=1`). Perubahan kurs saja tidak lagi
  memicu notifikasi; pesan dikirim kalau status harga berubah. (#8)
- Harga gTLD dari tabel harga gTLD digitalregistra (USD) ikut dicek, hanya untuk TLD yang dijual di
  WHMCS. Kurs USD ke IDR diambil dari open.er-api.com. Modal dihitung dengan kurs live. Register yang
  sedang promo reseller dihitung dari harga promonya. (#7)
- Kalau halaman gTLD atau layanan kurs gagal, domain .id tetap dicek dan error gTLD dikirim sekali. (#7)
- Register, renew, dan transfer dengan status dan harga yang sama digabung jadi satu baris. Pesan yang
  lebih dari 4.096 karakter dipecah per baris. (#7)
- Env baru: `GTLD_ENABLED`, `GTLD_ROUND_TO`, `USD_RATE_ROUND_TO`. (#7, #8)

## Log dan zona waktu

- Setiap pengecekan menulis baris `Cek selesai`, dan mode loop mencatat jam `Cek berikutnya`. (#6)
- Jam di log memakai zona waktu dari `TZ`, default `Asia/Jakarta`. (#6)

## Promo

- `PROMO` untuk item yang sengaja dijual di bawah rumus. Item promo ditampilkan di bagian 🏷️ dan tidak
  dihitung sebagai masalah; ada pengingat ℹ️ saat harganya kembali sesuai rumus. (#5)

## Telegram

- Notifikasi bisa dikirim ke topik tertentu di grup forum lewat `TELEGRAM_THREAD_ID`. (#2)
- Error dari Telegram menampilkan alasannya, misalnya `message thread not found`. (#2)

## WHMCS

- Error HTTP 403 dari WHMCS menampilkan pesan asli, misalnya `Invalid IP x.x.x.x`. (#3)

## Dokumentasi dan CI

- Bahasa di README, `.env.example`, komentar kode, dan pesan dirapikan. (#4)
- GitHub Actions memakai versi action berbasis Node 24. (#1)

## Rilis awal

- Pengecekan harga reseller domain .id (Gold Slab) digitalregistra terhadap harga jual WHMCS, dengan
  rumus `ROUNDUP(reseller × (1 + PPN + margin), ke ribuan)`.
- Notifikasi Telegram untuk perubahan harga reseller, harga di bawah modal, harga yang tidak sesuai rumus,
  dan TLD yang tidak dijual. Masalah yang sama hanya dikirim sekali.
- Docker, Docker Compose, dan image di GHCR.
