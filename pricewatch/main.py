import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Callable

from pricewatch import registra, telegram, whmcs
from pricewatch.check import Issue, Prices, Promo, find_issues, reseller_changes
from pricewatch.pricing import modal

log = logging.getLogger("pricewatch")

KIND_ORDER = {"loss": 0, "mismatch": 1, "missing": 2}


@dataclass
class Config:
    ppn: Decimal
    margin: Decimal
    state_file: Path
    whmcs_api_url: str | None = None
    whmcs_identifier: str | None = None
    whmcs_secret: str | None = None
    whmcs_currency_id: str | None = None
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_thread_id: str | None = None
    promo: Promo = frozenset()

    @classmethod
    def from_env(cls) -> "Config":
        def need(name: str) -> str:
            value = os.environ.get(name)
            if not value:
                sys.exit(f"Variabel {name} belum diisi. Lihat contohnya di .env.example")
            return value

        try:
            promo = parse_promo(os.environ.get("PROMO"))
        except ValueError as e:
            sys.exit(f"PROMO tidak valid: {e}")

        return cls(
            ppn=Decimal(os.environ.get("PPN_PERCENT", "11")),
            margin=Decimal(os.environ.get("MARGIN_PERCENT", "3")),
            state_file=Path(os.environ.get("STATE_FILE", "state.json")),
            whmcs_api_url=need("WHMCS_API_URL"),
            whmcs_identifier=need("WHMCS_IDENTIFIER"),
            whmcs_secret=need("WHMCS_SECRET"),
            whmcs_currency_id=os.environ.get("WHMCS_CURRENCY_ID") or None,
            telegram_token=need("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=need("TELEGRAM_CHAT_ID"),
            telegram_thread_id=os.environ.get("TELEGRAM_THREAD_ID") or None,
            promo=promo,
        )


def parse_promo(value: str | None) -> Promo:
    # Format: "my.id:register,biz.id:register"
    items = set()
    for raw in (value or "").split(","):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split(":")
        if len(parts) != 2:
            raise ValueError(f"'{raw}' harus berformat tld:aksi, misalnya my.id:register")
        tld, action = parts[0].strip().lstrip(".").lower(), parts[1].strip().lower()
        if not tld:
            raise ValueError(f"'{raw}' tidak punya nama TLD")
        if action not in whmcs.ACTIONS:
            raise ValueError(f"aksi '{action}' di '{raw}' harus salah satu dari {', '.join(whmcs.ACTIONS)}")
        items.add((tld, action))
    return frozenset(items)


def rp(value: int | Decimal) -> str:
    return "Rp" + f"{int(value):,}".replace(",", ".")


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"reseller": None, "issue_keys": [], "error": None}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def format_changes(changes: list[tuple[str, str, int | None, int | None]]) -> str:
    lines = ["📢 <b>Harga reseller digitalregistra (Gold Slab) berubah</b>"]
    for tld, action, before, after in changes:
        if before is None:
            lines.append(f"🆕 .{escape(tld)} {action}: {rp(after)}")
        elif after is None:
            lines.append(f"❌ .{escape(tld)} {action}: hilang dari tabel (sebelumnya {rp(before)})")
        else:
            arrow = "🔺" if after > before else "🔻"
            lines.append(f"{arrow} .{escape(tld)} {action}: {rp(before)} → {rp(after)}")
    return "\n".join(lines)


def format_issues(issues: list[Issue], ppn: Decimal) -> str:
    lines = [f"⚠️ <b>Harga jual WHMCS perlu dicek ({len(issues)})</b>"]
    for i in sorted(issues, key=lambda i: (KIND_ORDER[i.kind], i.tld, i.action or "")):
        name = f".{escape(i.tld)} {i.action}"
        if i.kind == "loss":
            lines.append(
                f"🔴 <b>RUGI</b> {name}: jual {rp(i.actual)} &lt; modal {rp(modal(i.reseller, ppn))}"
                f" → seharusnya {rp(i.expected)}"
            )
        elif i.kind == "mismatch":
            lines.append(f"🟡 {name}: jual {rp(i.actual)}, seharusnya {rp(i.expected)}")
        else:
            lines.append(f"⚪ {name}: tidak dijual di WHMCS (seharusnya {rp(i.expected)})")
    return "\n".join(lines)


def format_promo(issues: list[Issue]) -> str:
    lines = []
    active = [i for i in issues if i.kind == "promo"]
    if active:
        lines.append("🏷️ <b>Promo</b> (tidak dihitung sebagai masalah)")
        for i in active:
            lines.append(f"🏷️ .{escape(i.tld)} {i.action}: jual {rp(i.actual)}, harga normal {rp(i.expected)}")
    for i in issues:
        if i.kind == "promo_ended":
            lines.append(
                f"ℹ️ .{escape(i.tld)} {i.action} sudah kembali ke harga normal {rp(i.expected)}."
                " Kalau promonya sudah selesai, hapus dari PROMO."
            )
    return "\n".join(lines)


def run(
    cfg: Config,
    fetch_reseller: Callable[[], Prices],
    fetch_sell: Callable[[], Prices],
    notify: Callable[[str], None],
) -> None:
    state = load_state(cfg.state_file)
    try:
        reseller = fetch_reseller()
        sell = fetch_sell()
    except Exception as e:
        log.exception("Gagal mengambil data harga")
        error = f"{type(e).__name__}: {e}"
        # Error yang sama hanya dikirim sekali. Tanpa ini, setiap run mengirim pesan yang sama ke Telegram
        if state.get("error") != error:
            notify(f"🚨 <b>Pengecekan harga domain gagal</b>\n<code>{escape(error)}</code>")
            state["error"] = error
            save_state(cfg.state_file, state)
        return

    recovered = state.get("error") is not None
    first_run = state.get("reseller") is None
    changes = reseller_changes(state.get("reseller"), reseller)
    issues = find_issues(reseller, sell, cfg.ppn, cfg.margin, promo=cfg.promo)
    issue_keys = sorted(i.key for i in issues)
    alerts = [i for i in issues if i.is_alert]
    for tld, action in sorted(cfg.promo):
        if action not in reseller.get(tld, {}):
            log.warning("PROMO %s:%s tidak ada di tabel digitalregistra, diabaikan", tld, action)

    parts = []
    if changes:
        parts.append(format_changes(changes))
    if first_run or changes or issue_keys != state.get("issue_keys"):
        if alerts:
            parts.append(format_issues(alerts, cfg.ppn))
        elif any(i.kind == "promo" for i in issues):
            parts.append("✅ Semua harga jual domain Indonesia sudah sesuai rumus, kecuali promo di bawah.")
        else:
            parts.append(f"✅ Semua harga jual domain Indonesia ({len(reseller)} TLD) sudah sesuai rumus.")
        promo_text = format_promo(issues)
        if promo_text:
            parts.append(promo_text)
    if recovered and not parts:
        parts.append("✅ Pengecekan harga domain kembali normal. Tidak ada perubahan harga.")

    if parts:
        notify("\n\n".join(parts))
    log.info(
        "Cek selesai: %d TLD, %d masalah, %d promo, %s",
        len(reseller),
        len(alerts),
        sum(i.kind == "promo" for i in issues),
        "notifikasi dikirim" if parts else "tidak ada notifikasi",
    )
    save_state(cfg.state_file, {"reseller": reseller, "issue_keys": issue_keys, "error": None})


def run_forever(
    job: Callable[[], None],
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    max_runs: int | None = None,
) -> None:
    runs = 0
    while True:
        try:
            job()
        except Exception:
            # Error di satu run, misalnya Telegram sedang down, tidak boleh mematikan container
            log.exception("Pengecekan gagal, dicoba lagi di jadwal berikutnya")
        runs += 1
        if max_runs is not None and runs >= max_runs:
            return
        next_run = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
        log.info("Cek berikutnya sekitar %s UTC", next_run.strftime("%H:%M:%S"))
        sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cocokkan harga reseller digitalregistra dengan harga jual di WHMCS")
    parser.add_argument("--dry-run", action="store_true", help="cetak pesan ke terminal tanpa mengirim ke Telegram")
    parser.add_argument("--test-telegram", action="store_true", help="kirim pesan tes ke Telegram, lalu keluar")
    parser.add_argument(
        "--loop", action="store_true", help="cek terus setiap INTERVAL_MINUTES menit (dipakai di Docker)"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(message)s")
    # Jam di log selalu UTC, sama dengan jadwal "Cek berikutnya", walaupun TZ host bukan UTC
    logging.Formatter.converter = time.gmtime

    cfg = Config.from_env()

    def notify(text: str) -> None:
        if args.dry_run:
            print(text, end="\n\n")
        else:
            telegram.send_message(cfg.telegram_token, cfg.telegram_chat_id, text, thread_id=cfg.telegram_thread_id)

    if args.test_telegram:
        notify("🔔 Tes notifikasi Pricewatch digitalregistra")
        return

    def fetch_sell() -> Prices:
        payload = whmcs.fetch_tld_pricing(
            cfg.whmcs_api_url, cfg.whmcs_identifier, cfg.whmcs_secret, cfg.whmcs_currency_id
        )
        return whmcs.parse_tld_pricing(payload)

    def job() -> None:
        run(
            cfg,
            fetch_reseller=lambda: registra.parse_gold_slab(registra.fetch_html()),
            fetch_sell=fetch_sell,
            notify=notify,
        )

    if args.loop:
        minutes = float(os.environ.get("INTERVAL_MINUTES", "360"))
        log.info("Mode loop: cek setiap %s menit", minutes)
        run_forever(job, interval_seconds=minutes * 60)
    else:
        job()


if __name__ == "__main__":
    main()
