from pathlib import Path

import pytest

from pricewatch.registra import ScrapeError, parse_gold_slab

FIXTURE = (Path(__file__).parent / "fixtures" / "registra.html").read_text(encoding="utf-8")


def test_parse_gold_slab_ambil_kolom_gold():
    prices = parse_gold_slab(FIXTURE)
    # .web.id beda per slab: Bronze 47.000, Silver 46.000, Gold 45.000
    assert prices["web.id"] == {"register": 45_000, "renew": 45_000, "transfer": 45_000}
    assert prices["co.id"] == {"register": 270_000, "renew": 270_000, "transfer": 270_000}


def test_parse_gold_slab_normalisasi_tld():
    prices = parse_gold_slab(FIXTURE)
    # ".ID" di tabel → "id" (format key WHMCS)
    assert "id" in prices
    assert prices["id"]["register"] == 210_000


def test_parse_gold_slab_lewati_baris_deposit():
    prices = parse_gold_slab(FIXTURE)
    assert set(prices) == {
        "co.id", "my.id", "biz.id", "web.id", "or.id", "ac.id", "sch.id", "ponpes.id", "id",
    }


def test_parse_gold_slab_gagal_kalau_tabel_hilang():
    with pytest.raises(ScrapeError):
        parse_gold_slab("<html><body>maintenance</body></html>")


def test_parse_gold_slab_gagal_kalau_kolom_gold_hilang():
    html = FIXTURE.replace("Gold Slab", "Platinum Slab")
    with pytest.raises(ScrapeError):
        parse_gold_slab(html)
