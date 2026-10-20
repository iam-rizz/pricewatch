from decimal import ROUND_CEILING, Decimal

import requests

URL = "https://open.er-api.com/v6/latest/USD"
# Selisih tambahan sebelum kurs efektif boleh turun: round_to // 5 (Rp100 untuk kelipatan Rp500)
HYSTERESIS_DIVISOR = 5


class KursError(Exception):
    pass


def fetch_rate_payload(timeout: float = 30) -> dict:
    resp = requests.get(URL, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def parse_open_er_api(payload: dict) -> Decimal:
    if payload.get("result") != "success":
        raise KursError(f"open.er-api.com gagal: {payload.get('error-type', 'tanpa pesan error')}")
    rate = payload.get("rates", {}).get("IDR")
    if rate is None:
        raise KursError("open.er-api.com tidak mengirim kurs IDR")
    return Decimal(str(rate))


def effective_rate(live: Decimal, round_to: int, previous: int | None = None) -> int:
    # Kurs live bergerak tiap hari; dibulatkan ke atas supaya harga seharusnya hanya berubah
    # saat kurs melewati kelipatan round_to, sekaligus memberi bantalan untuk margin
    rounded = int((live / round_to).to_integral_value(rounding=ROUND_CEILING) * round_to)
    if previous is None or rounded >= previous:
        # Naik langsung supaya margin tidak tergerus
        return rounded
    # Turun hanya kalau live sudah turun satu kelipatan penuh ditambah selisih kecil. Tanpa ini,
    # kurs live yang bergerak di sekitar batas kelipatan membuat kurs efektif bolak-balik setiap hari
    if live <= previous - round_to - round_to // HYSTERESIS_DIVISOR:
        return rounded
    return previous
