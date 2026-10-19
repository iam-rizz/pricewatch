import pytest

from pricewatch import whmcs
from pricewatch.whmcs import WhmcsError, parse_tld_pricing

SAMPLE = {
    "result": "success",
    "currency": {"id": 1, "code": "IDR"},
    "pricing": {
        "co.id": {
            "register": {"1": "308000.00", "2": "616000.00"},
            "transfer": {"1": "308000.00"},
            "renew": {"1": "308000.00"},
        },
        "web.id": {
            "register": {"1": "52000.00"},
            "transfer": {"1": "-1.00"},
            "renew": {"1": "52000.00"},
        },
        "com": {
            "register": {"1": "180000.00"},
            "transfer": {"1": "180000.00"},
            "renew": {"1": "180000.00"},
        },
    },
}


def test_parse_ambil_harga_1_tahun():
    prices = parse_tld_pricing(SAMPLE)
    assert prices["co.id"] == {"register": 308_000, "renew": 308_000, "transfer": 308_000}


def test_parse_harga_minus_satu_berarti_tidak_dijual():
    prices = parse_tld_pricing(SAMPLE)
    assert prices["web.id"] == {"register": 52_000, "renew": 52_000}


def test_parse_error_dari_api():
    with pytest.raises(WhmcsError, match="Invalid IP"):
        parse_tld_pricing({"result": "error", "message": "Invalid IP 1.2.3.4"})


class FakeResponse:
    def __init__(self, status, body=None, text=""):
        self.status_code = status
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


def test_fetch_403_json_whmcs_tetap_dibaca_pesannya(monkeypatch):
    # Untuk Invalid IP atau kredensial salah, WHMCS membalas HTTP 403 berisi JSON
    body = {"result": "error", "message": "Invalid IP 203.0.113.7"}
    monkeypatch.setattr(whmcs.requests, "post", lambda *a, **k: FakeResponse(403, body))
    payload = whmcs.fetch_tld_pricing("https://x/includes/api.php", "id", "secret")
    with pytest.raises(WhmcsError, match="Invalid IP 203.0.113.7"):
        parse_tld_pricing(payload)


def test_fetch_403_bukan_json_lempar_whmcs_error_dengan_status(monkeypatch):
    # Misalnya WAF atau ModSecurity yang membalas dengan halaman HTML
    monkeypatch.setattr(
        whmcs.requests, "post", lambda *a, **k: FakeResponse(403, text="<html><title>Access denied</title></html>")
    )
    with pytest.raises(WhmcsError, match="HTTP 403.*Access denied"):
        whmcs.fetch_tld_pricing("https://x/includes/api.php", "id", "secret")
