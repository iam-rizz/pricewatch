from decimal import ROUND_CEILING, Decimal

import requests

URL = "https://open.er-api.com/v6/latest/USD"


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


def effective_rate(live: Decimal, round_to: int) -> int:
    # Kurs live bergerak tiap hari; dibulatkan ke atas supaya harga seharusnya hanya berubah
    # saat kurs melewati kelipatan round_to, sekaligus memberi bantalan untuk margin
    return int((live / round_to).to_integral_value(rounding=ROUND_CEILING) * round_to)
