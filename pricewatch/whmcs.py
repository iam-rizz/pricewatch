from decimal import Decimal

import requests

ACTIONS = ("register", "renew", "transfer")
ONE_YEAR = "1"


class WhmcsError(Exception):
    pass


def fetch_tld_pricing(
    api_url: str, identifier: str, secret: str, currency_id: str | None = None, timeout: float = 30
) -> dict:
    data = {
        "action": "GetTLDPricing",
        "identifier": identifier,
        "secret": secret,
        "responsetype": "json",
    }
    if currency_id:
        data["currencyid"] = currency_id
    resp = requests.post(api_url, data=data, timeout=timeout)
    # Untuk Invalid IP atau kredensial salah, WHMCS membalas HTTP 403 berisi JSON.
    # raise_for_status() akan membuang pesan itu, jadi JSON-nya dibaca dulu
    try:
        payload = resp.json()
    except ValueError:
        snippet = " ".join(resp.text.split())[:200]
        raise WhmcsError(f"HTTP {resp.status_code} dari {api_url} (bukan JSON WHMCS): {snippet}") from None
    if not isinstance(payload, dict) or "result" not in payload:
        raise WhmcsError(f"HTTP {resp.status_code} dari {api_url}: respons tidak dikenal")
    return payload


def parse_tld_pricing(payload: dict) -> dict[str, dict[str, int]]:
    if payload.get("result") != "success":
        raise WhmcsError(payload.get("message", "GetTLDPricing gagal tanpa pesan error"))

    prices: dict[str, dict[str, int]] = {}
    for tld, info in payload.get("pricing", {}).items():
        per_action = {}
        for action in ACTIONS:
            raw = (info.get(action) or {}).get(ONE_YEAR)
            if raw is None:
                continue
            value = Decimal(str(raw))
            if value < 0:
                continue  # -1 di WHMCS berarti aksi ini tidak dijual
            per_action[action] = int(value)
        prices[tld.lstrip(".").lower()] = per_action
    return prices
