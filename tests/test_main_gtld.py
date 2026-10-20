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
    # Angka di tes ini ditulis untuk kurs dibulatkan ke kelipatan Rp500 (18.055 → 18.500)
    return Config(ppn=Decimal("11"), margin=Decimal("3"), state_file=tmp_path / "state.json", usd_rate_round_to=500)


def raise_or(value):
    def fetch():
        if isinstance(value, Exception):
            raise value
        return value

    return fetch


def go(cfg, gtld=GTLD, sell=SELL_OK, rate="18055.12", id_reseller=ID_RESELLER):
    sent = []
    run(
        cfg,
        fetch_reseller=lambda: id_reseller,
        fetch_sell=lambda: sell,
        notify=sent.append,
        fetch_gtld=raise_or(gtld),
        fetch_rate=raise_or(rate if isinstance(rate, Exception) else Decimal(rate)),
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


def test_kurs_live_bolak_balik_di_batas_hanya_sekali_notif(cfg):
    # 11,75 × 19.000 × 1,14 = 254.505 → 255.000, sesuai kurs 19.000
    sell = {**ID_SELL, "com": {"register": 255_000, "renew": 255_000}}
    go(cfg, sell=sell, rate="18499.9")
    assert len(go(cfg, sell=sell, rate="18500.1")) == 1  # naik ke 19.000
    for live in ("18499.9", "18500.1", "18499.9"):
        assert go(cfg, sell=sell, rate=live) == []


def test_kurs_gagal_domain_id_tetap_dicek(cfg):
    go(cfg)
    naik = {"web.id": {"register": 47_000}}
    text = "\n".join(go(cfg, rate=ConnectionError("open.er-api.com down"), id_reseller=naik))
    assert "47.000" in text  # perubahan harga .id tetap dikabarkan
    assert "gTLD" in text and "open.er-api.com down" in text


def test_kurs_gagal_dikirim_sekali_saja(cfg):
    go(cfg)
    go(cfg, rate=ConnectionError("down"))
    assert go(cfg, rate=ConnectionError("down")) == []


def test_pulih_dari_kurs_gagal_tidak_mengulang_masalah_gtld(cfg):
    sell = {**ID_SELL, "com": {"register": 248_000, "renew": 240_500}}  # .com renew 🟡
    go(cfg, sell=sell)
    go(cfg, sell=sell, rate=ConnectionError("down"))
    [text] = go(cfg, sell=sell)
    assert "normal" in text.lower()
    assert ".com" not in text  # masalah .com sudah pernah dikirim
    assert go(cfg, sell=sell) == []


def test_halaman_gtld_gagal_domain_id_tetap_dicek(cfg):
    from pricewatch.registra import ScrapeError

    go(cfg)
    naik = {"web.id": {"register": 47_000}}
    text = "\n".join(go(cfg, gtld=ScrapeError("Header tabel gTLD berubah"), id_reseller=naik))
    assert "47.000" in text and "Header tabel gTLD berubah" in text


def test_promo_berlaku_untuk_gtld(tmp_path):
    cfg = Config(
        ppn=Decimal("11"),
        margin=Decimal("3"),
        state_file=tmp_path / "state.json",
        promo=frozenset({("com", "register")}),
    )
    sell = {**ID_SELL, "com": {"register": 30_000, "renew": 248_000}}
    [text] = go(cfg, sell=sell)
    assert "RUGI" not in text and "🏷️ .com register" in text


def test_tanpa_gtld_perilaku_lama(tmp_path):
    import json

    cfg = Config(ppn=Decimal("11"), margin=Decimal("3"), state_file=tmp_path / "state.json")
    sent = []
    run(cfg, fetch_reseller=lambda: ID_RESELLER, fetch_sell=lambda: SELL_OK, notify=sent.append)
    assert sent == ["✅ Semua harga jual (1 TLD) sudah sesuai rumus."]
    state = json.loads(cfg.state_file.read_text())
    assert "gtld" not in state and "kurs" not in state


def test_upgrade_dari_state_lama_tanpa_gtld(cfg):
    import json

    cfg.state_file.write_text(json.dumps({"reseller": ID_RESELLER, "issue_keys": [], "error": None}))
    assert go(cfg) == []  # semua gTLD sesuai, tidak ada yang perlu dikabarkan
    sell = {**ID_SELL, "com": {"register": 248_000, "renew": 240_500}}
    cfg.state_file.write_text(json.dumps({"reseller": ID_RESELLER, "issue_keys": [], "error": None}))
    [text] = go(cfg, sell=sell)
    assert "🟡 .com renew" in text and "📢" not in text


def test_fetch_gtld_tanpa_fetch_rate_ditolak(cfg):
    with pytest.raises(ValueError, match="fetch_rate"):
        run(cfg, fetch_reseller=lambda: ID_RESELLER, fetch_sell=lambda: SELL_OK, notify=print, fetch_gtld=lambda: GTLD)


@pytest.fixture
def cfg_live(tmp_path):
    return Config(ppn=Decimal("11"), margin=Decimal("3"), state_file=tmp_path / "state.json")


# Kurs live 18.055,12 → 18.056: 11,75 × 18.056 × 1,14 = 241.858,1 → 242.000
SELL_LIVE = {**ID_SELL, "com": {"register": 242_000, "renew": 242_000}}


def test_default_kurs_ikut_live_dibulatkan_ke_rupiah(cfg_live):
    [text] = go(cfg_live, sell=SELL_LIVE)
    assert "✅" in text and "Rp18.056" in text and "kurs live" in text and "kelipatan" not in text


def test_kurs_bergerak_tanpa_mengubah_status_tidak_kirim_notif(cfg_live):
    go(cfg_live, sell=SELL_LIVE)
    # 18.057: 11,75 × 18.057 × 1,14 = 241.871,5 → tetap 242.000
    assert go(cfg_live, sell=SELL_LIVE, rate="18056.50") == []


def test_kurs_bergerak_mengubah_harga_seharusnya_kirim_notif(cfg_live):
    go(cfg_live, sell=SELL_LIVE)
    # 18.100: 11,75 × 18.100 × 1,14 = 242.452,5 → 242.500, harga 242.000 jadi 🟡
    text = "\n".join(go(cfg_live, sell=SELL_LIVE, rate="18099.40"))
    assert "🟡 .com" in text and "Rp242.500" in text and "Rp18.056" in text and "Rp18.100" in text
