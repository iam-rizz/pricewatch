import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Callable

from pricewatch import registra, telegram, whmcs
from pricewatch.check import Issue, Prices, find_issues, reseller_changes
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

    @classmethod
    def from_env(cls) -> "Config":
        def need(name: str) -> str:
            value = os.environ.get(name)
            if not value:
                sys.exit(f"Env {name} belum di-set (lihat .env.example)")
            return value

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
        )


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
        log.exception("Gagal ambil data harga")
        error = f"{type(e).__name__}: {e}"
        # Kirim sekali per jenis error, supaya cron tiap jam tidak spam Telegram
        if state.get("error") != error:
            notify(f"🚨 <b>Pengecekan harga domain gagal</b>\n<code>{escape(error)}</code>")
            state["error"] = error
            save_state(cfg.state_file, state)
        return

    recovered = state.get("error") is not None
    first_run = state.get("reseller") is None
    changes = reseller_changes(state.get("reseller"), reseller)
    issues = find_issues(reseller, sell, cfg.ppn, cfg.margin)
    issue_keys = sorted(i.key for i in issues)

    parts = []
    if changes:
        parts.append(format_changes(changes))
    if first_run or changes or issue_keys != state.get("issue_keys"):
        if issues:
            parts.append(format_issues(issues, cfg.ppn))
        else:
            parts.append(f"✅ Semua harga jual domain Indonesia ({len(reseller)} TLD) sudah sesuai rumus.")
    if recovered and not parts:
        parts.append("✅ Pengecekan harga domain kembali normal. Tidak ada perubahan harga.")

    if parts:
        notify("\n\n".join(parts))
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
            # Satu run gagal (mis. Telegram down) jangan matikan container; coba lagi run berikutnya
            log.exception("Run gagal, lanjut ke jadwal berikutnya")
        runs += 1
        if max_runs is not None and runs >= max_runs:
            return
        sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pantau harga reseller digitalregistra vs harga jual WHMCS")
    parser.add_argument("--dry-run", action="store_true", help="cetak pesan ke terminal, tidak kirim Telegram")
    parser.add_argument("--test-telegram", action="store_true", help="kirim pesan tes ke Telegram lalu keluar")
    parser.add_argument("--loop", action="store_true", help="jalan terus tiap INTERVAL_MINUTES (untuk Docker)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

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
        log.info("Mode loop, cek tiap %s menit", minutes)
        run_forever(job, interval_seconds=minutes * 60)
    else:
        job()


if __name__ == "__main__":
    main()
