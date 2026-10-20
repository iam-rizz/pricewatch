from decimal import Decimal

import pytest

from pricewatch.main import Config, run

ID_RESELLER = {"web.id": {"register": 45_000}}
ID_SELL = {"web.id": {"register": 52_000}}
# .com dijual, .zone tidak dijual di WHMCS
GTLD = {
    "com": {"register": Decimal("11.75"), "renew": Decimal("11.75")},
    "zone": {"register": Decimal("10.24"), "renew": Decimal("33.34")},
}
# 11,75 × 18.500 × 1,14 = 247.807,5 → 248.000
SELL_OK = {**ID_SELL, "com": {"register": 248_000, "renew": 248_000}}


@pytest.fixture
def cfg(tmp_path):
    return Config(ppn=Decimal("11"), margin=Decimal("3"), state_file=tmp_path / "state.json")


def go(cfg, gtld=GTLD, sell=SELL_OK, rate="18055.12"):
    sent = []
    run(
        cfg,
        fetch_reseller=lambda: ID_RESELLER,
        fetch_sell=lambda: sell,
        notify=sent.append,
        fetch_gtld=lambda: gtld,
        fetch_rate=lambda: Decimal(rate),
    )
    return sent


def test_gtld_sesuai_rumus_dengan_kurs_efektif(cfg):
    [text] = go(cfg)
    assert "sesuai" in text
    assert "Rp18.500" in text  # kurs efektif ditampilkan


def test_gtld_yang_tidak_dijual_tidak_dilaporkan(cfg):
    [text] = go(cfg)
    assert ".zone" not in text


def test_gtld_rugi_dilaporkan_dalam_rupiah(cfg):
    # modal pakai kurs live 18.055,12: 11,75 × 18.055,12 × 1,11 = 235.489 → 230.000 rugi
    sell = {**ID_SELL, "com": {"register": 248_000, "renew": 230_000}}
    [text] = go(cfg, sell=sell)
    assert "RUGI" in text and ".com renew" in text and "Rp230.000" in text and "Rp248.000" in text


def test_gtld_di_atas_modal_kurs_live_bukan_rugi(cfg):
    sell = {**ID_SELL, "com": {"register": 248_000, "renew": 240_500}}
    [text] = go(cfg, sell=sell)
    assert "RUGI" not in text and "🟡 .com renew" in text


def test_run_kedua_data_sama_diam(cfg):
    go(cfg)
    assert go(cfg) == []


def test_perubahan_harga_usd_dikirim_dalam_dolar(cfg):
    go(cfg)
    naik = {**GTLD, "com": {"register": Decimal("11.75"), "renew": Decimal("12.10")}}
    text = "\n".join(go(cfg, gtld=naik))
    assert "$11.75" in text and "$12.10" in text


def test_perubahan_harga_usd_tld_tidak_dijual_diam(cfg):
    go(cfg)
    zone_naik = {**GTLD, "zone": {"register": Decimal("10.24"), "renew": Decimal("40.00")}}
    assert go(cfg, gtld=zone_naik) == []


def test_kurs_live_bergerak_dalam_kelipatan_sama_diam(cfg):
    go(cfg, rate="18055.12")
    assert go(cfg, rate="18310.50") == []


def test_kurs_efektif_berubah_dikirim(cfg):
    go(cfg, rate="18055.12")
    text = "\n".join(go(cfg, rate="18530.00"))
    assert "Rp18.500" in text and "Rp19.000" in text
