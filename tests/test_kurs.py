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


def test_effective_rate_naik_langsung_kalau_live_melewati_kurs_sebelumnya():
    assert effective_rate(Decimal("18500.10"), round_to=500, previous=18_500) == 19_000


def test_effective_rate_tidak_bolak_balik_di_batas_kelipatan():
    rate = effective_rate(Decimal("18499.9"), round_to=500)
    for live in ("18500.1", "18499.9", "18500.1", "18499.9"):
        rate = effective_rate(Decimal(live), round_to=500, previous=rate)
    assert rate == 19_000


def test_effective_rate_tetap_selama_turunnya_belum_cukup():
    # Turun baru dianggap kalau live <= sebelumnya - kelipatan - 100
    assert effective_rate(Decimal("18400.01"), round_to=500, previous=19_000) == 19_000


def test_effective_rate_turun_kalau_live_turun_cukup_jauh():
    assert effective_rate(Decimal("18400"), round_to=500, previous=19_000) == 18_500
    assert effective_rate(Decimal("17200"), round_to=500, previous=19_000) == 17_500
