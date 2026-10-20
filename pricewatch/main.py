import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone, tzinfo
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pricewatch import gtld, kurs, registra, telegram, whmcs
from pricewatch.check import Issue, Prices, Promo, find_issues, reseller_changes

log = logging.getLogger("pricewatch")

DEFAULT_TZ = "Asia/Jakarta"


def local_tz() -> tzinfo:
    name = os.environ.get("TZ") or DEFAULT_TZ
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("Zona waktu TZ=%s tidak dikenal, log memakai UTC", name)
        return timezone.utc


class LocalFormatter(logging.Formatter):
    # Pakai zoneinfo, bukan time.localtime, supaya hasilnya sama di host maupun container
    # dan tidak bergantung pada database zona waktu di sistem
    def __init__(self, fmt: str, tz: tzinfo):
        super().__init__(fmt)
        self.tz = tz

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        return datetime.fromtimestamp(record.created, self.tz).strftime(datefmt or "%Y-%m-%d %H:%M:%S %Z")

KIND_ORDER = {"loss": 0, "mismatch": 1, "missing": 2}
ACTION_ORDER = {action: n for n, action in enumerate(whmcs.ACTIONS)}


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
    gtld_enabled: bool = True
    gtld_round_to: int = 500
    usd_rate_round_to: int = 500

    @classmethod
    def from_env(cls) -> "Config":
        def need(name: str) -> str:
            value = os.environ.get(name)
            if not value:
                sys.exit(f"Variabel {name} belum diisi. Lihat contohnya di .env.example")
            return value

        def positive_int(name: str, default: str) -> int:
            raw = os.environ.get(name) or default
            try:
                value = int(raw)
            except ValueError:
                value = 0
            if value <= 0:
                sys.exit(f"{name} harus bilangan bulat positif, misalnya 500 (sekarang: {raw})")
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
            gtld_enabled=os.environ.get("GTLD_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off"),
            gtld_round_to=positive_int("GTLD_ROUND_TO", "500"),
            usd_rate_round_to=positive_int("USD_RATE_ROUND_TO", "500"),
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


def usd(value: Decimal) -> str:
    return f"${value:.2f}"


def gtld_to_json(prices: Prices) -> dict:
    return {tld: {action: str(v) for action, v in per.items()} for tld, per in prices.items()}


def gtld_from_json(data: dict | None) -> Prices | None:
    if data is None:
        return None
    return {tld: {action: Decimal(v) for action, v in per.items()} for tld, per in data.items()}


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"reseller": None, "issue_keys": [], "error": None}
    return json.loads(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def format_changes(
    changes: list[tuple[str, str, int | None, int | None]],
    title: str = "Harga reseller digitalregistra (Gold Slab) berubah",
    money: Callable[[int | Decimal], str] = rp,
) -> str:
    lines = [f"📢 <b>{title}</b>"]
    for tld, action, before, after in changes:
        if before is None:
            lines.append(f"🆕 .{escape(tld)} {action}: {money(after)}")
        elif after is None:
            lines.append(f"❌ .{escape(tld)} {action}: hilang dari tabel (sebelumnya {money(before)})")
        else:
            arrow = "🔺" if after > before else "🔻"
            lines.append(f"{arrow} .{escape(tld)} {action}: {money(before)} → {money(after)}")
    return "\n".join(lines)


def format_issues(issues: list[Issue]) -> str:
    # Register, renew, dan transfer dengan status dan harga yang sama cukup satu baris,
    # supaya pesan untuk puluhan gTLD tidak melewati batas 4.096 karakter Telegram
    groups: dict[tuple, list[Issue]] = {}
    for i in issues:
        groups.setdefault((KIND_ORDER[i.kind], i.tld, i.actual, i.expected), []).append(i)
    lines = [f"⚠️ <b>Harga jual WHMCS perlu dicek ({len(groups)})</b>"]
    for key in sorted(groups, key=lambda k: (k[0], k[1], min(ACTION_ORDER[i.action] for i in groups[k]))):
        group = sorted(groups[key], key=lambda i: ACTION_ORDER[i.action])
        i = group[0]
        name = f".{escape(i.tld)} {', '.join(g.action for g in group)}"
        if i.kind == "loss":
            lines.append(
                f"🔴 <b>RUGI</b> {name}: jual {rp(i.actual)} &lt; modal {rp(i.cost)}"
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
    fetch_gtld: Callable[[], Prices] | None = None,
    fetch_rate: Callable[[], Decimal] | None = None,
) -> None:
    state = load_state(cfg.state_file)
    try:
        reseller = fetch_reseller()
        sell = fetch_sell()
        gtld_prices = fetch_gtld() if fetch_gtld else None
        live_rate = fetch_rate() if fetch_gtld and fetch_rate else None
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

    gtld_changes: list = []
    gtld_sold = 0
    rate = rate_changed = None
    if gtld_prices is not None and live_rate is not None:
        rate = kurs.effective_rate(live_rate, cfg.usd_rate_round_to)
        old_rate = state.get("kurs")
        rate_changed = old_rate is not None and old_rate != rate
        # Perubahan harga gTLD yang tidak Anda jual tidak perlu dikabarkan
        gtld_changes = [c for c in reseller_changes(gtld_from_json(state.get("gtld")), gtld_prices) if c[0] in sell]
        gtld_sold = sum(tld in sell for tld in gtld_prices)
        issues += find_issues(
            gtld_prices,
            sell,
            cfg.ppn,
            cfg.margin,
            promo=cfg.promo,
            to_idr=lambda price: price * rate,
            cost_to_idr=lambda price: price * live_rate,
            round_to=cfg.gtld_round_to,
            only_sold=True,
        )

    issue_keys = sorted(i.key for i in issues)
    alerts = [i for i in issues if i.is_alert]
    for tld, action in sorted(cfg.promo):
        if action not in reseller.get(tld, {}) and action not in (gtld_prices or {}).get(tld, {}):
            log.warning("PROMO %s:%s tidak ada di tabel digitalregistra, diabaikan", tld, action)

    parts = []
    if changes:
        parts.append(format_changes(changes))
    if gtld_changes:
        parts.append(format_changes(gtld_changes, title="Harga reseller gTLD digitalregistra berubah", money=usd))
    if rate_changed:
        parts.append(
            f"💱 Kurs efektif berubah: {rp(state['kurs'])} → {rp(rate)} per USD (kurs live {rp(live_rate)})"
        )
    if first_run or changes or gtld_changes or rate_changed or issue_keys != state.get("issue_keys"):
        scope = f"{len(reseller)} TLD .id, {gtld_sold} gTLD" if rate is not None else f"{len(reseller)} TLD"
        if alerts:
            parts.append(format_issues(alerts))
        elif any(i.kind == "promo" for i in issues):
            parts.append(f"✅ Semua harga jual ({scope}) sudah sesuai rumus, kecuali promo di bawah.")
        else:
            parts.append(f"✅ Semua harga jual ({scope}) sudah sesuai rumus.")
        promo_text = format_promo(issues)
        if promo_text:
            parts.append(promo_text)
        if rate is not None and not rate_changed:
            parts.append(
                f"💱 Kurs gTLD {rp(rate)} per USD (kurs live {rp(live_rate)},"
                f" dibulatkan ke atas ke kelipatan {rp(cfg.usd_rate_round_to)})"
            )
    if recovered and not parts:
        parts.append("✅ Pengecekan harga domain kembali normal. Tidak ada perubahan harga.")

    if parts:
        notify("\n\n".join(parts))
    log.info(
        "Cek selesai: %d TLD, %d masalah, %d promo, %s",
        len(reseller) + gtld_sold,
        len(alerts),
        sum(i.kind == "promo" for i in issues),
        "notifikasi dikirim" if parts else "tidak ada notifikasi",
    )
    new_state = {"reseller": reseller, "issue_keys": issue_keys, "error": None}
    if rate is not None:
        new_state.update(gtld=gtld_to_json(gtld_prices), kurs=rate)
    save_state(cfg.state_file, new_state)


def run_forever(
    job: Callable[[], None],
    interval_seconds: float,
    sleep: Callable[[float], None] = time.sleep,
    max_runs: int | None = None,
    tz: tzinfo = timezone.utc,
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
        next_run = datetime.now(tz) + timedelta(seconds=interval_seconds)
        log.info("Cek berikutnya sekitar %s", next_run.strftime("%H:%M:%S %Z"))
        sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Cocokkan harga reseller digitalregistra dengan harga jual di WHMCS")
    parser.add_argument("--dry-run", action="store_true", help="cetak pesan ke terminal tanpa mengirim ke Telegram")
    parser.add_argument("--test-telegram", action="store_true", help="kirim pesan tes ke Telegram, lalu keluar")
    parser.add_argument(
        "--loop", action="store_true", help="cek terus setiap INTERVAL_MINUTES menit (dipakai di Docker)"
    )
    args = parser.parse_args()
    tz = local_tz()
    handler = logging.StreamHandler()
    handler.setFormatter(LocalFormatter("%(asctime)s %(levelname)s %(message)s", tz=tz))
    logging.basicConfig(level=logging.INFO, handlers=[handler])

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
            fetch_gtld=(lambda: gtld.parse_gtld(gtld.fetch_html())) if cfg.gtld_enabled else None,
            fetch_rate=lambda: kurs.parse_open_er_api(kurs.fetch_rate_payload()),
        )

    if args.loop:
        minutes = float(os.environ.get("INTERVAL_MINUTES", "360"))
        log.info("Mode loop: cek setiap %s menit", minutes)
        run_forever(job, interval_seconds=minutes * 60, tz=tz)
    else:
        job()


if __name__ == "__main__":
    main()
