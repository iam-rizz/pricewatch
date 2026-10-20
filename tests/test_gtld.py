from decimal import Decimal
from pathlib import Path

import pytest

from pricewatch.gtld import parse_gtld
from pricewatch.registra import ScrapeError

FIXTURE = (Path(__file__).parent / "fixtures" / "gtld.html").read_text(encoding="utf-8")


def test_parse_gtld_harga_usd():
    prices = parse_gtld(FIXTURE)
    assert prices["com"] == {"register": Decimal("11.75"), "renew": Decimal("11.75"), "transfer": Decimal("11.75")}


def test_parse_gtld_register_promo_pakai_harga_promo():
    # <del>14.90</del> 1.91 → promo reseller diikuti
    prices = parse_gtld(FIXTURE)
    assert prices["xyz"]["register"] == Decimal("1.91")
    assert prices["xyz"]["renew"] == Decimal("14.90")


def test_parse_gtld_tld_bertitik():
    assert "it.com" in parse_gtld(FIXTURE)


def test_parse_gtld_semua_baris():
    assert set(parse_gtld(FIXTURE)) == {"ac", "com", "it.com", "top", "xyz"}


def test_parse_gtld_gagal_kalau_tabel_hilang():
    with pytest.raises(ScrapeError):
        parse_gtld("<html><body>maintenance</body></html>")


def test_parse_gtld_gagal_kalau_kolom_berubah():
    with pytest.raises(ScrapeError):
        parse_gtld(FIXTURE.replace("Renewal", "Perpanjangan"))


def test_parse_gtld_gagal_kalau_harga_bukan_angka():
    with pytest.raises(ScrapeError, match="com"):
        parse_gtld(FIXTURE.replace("<td>11.75</td>", "<td>hubungi kami</td>", 1))
