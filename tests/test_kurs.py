from decimal import Decimal

import pytest

from pricewatch.kurs import KursError, effective_rate, parse_open_er_api


def test_parse_open_er_api_ambil_idr():
    payload = {"result": "success", "base_code": "USD", "rates": {"IDR": 18055.122099, "EUR": 0.86}}
    assert parse_open_er_api(payload) == Decimal("18055.122099")


def test_parse_open_er_api_error():
    with pytest.raises(KursError, match="unsupported-code"):
        parse_open_er_api({"result": "error", "error-type": "unsupported-code"})


def test_parse_open_er_api_tanpa_idr():
    with pytest.raises(KursError, match="IDR"):
        parse_open_er_api({"result": "success", "base_code": "USD", "rates": {"EUR": 0.86}})


def test_effective_rate_dibulatkan_ke_atas_500():
    assert effective_rate(Decimal("18055.12"), round_to=500) == 18_500
    assert effective_rate(Decimal("18000"), round_to=500) == 18_000
    assert effective_rate(Decimal("18000.01"), round_to=500) == 18_500
