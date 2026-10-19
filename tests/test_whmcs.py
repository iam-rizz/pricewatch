import pytest

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
