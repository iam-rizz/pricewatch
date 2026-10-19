import json
from decimal import Decimal

import pytest

from pricewatch.main import Config, run
from pricewatch.registra import ScrapeError

RESELLER = {"web.id": {"register": 45_000}, "co.id": {"register": 270_000}}
SELL_OK = {"web.id": {"register": 52_000}, "co.id": {"register": 308_000}}
SELL_BAD = {"web.id": {"register": 49_000}, "co.id": {"register": 308_000}}


@pytest.fixture
def cfg(tmp_path):
    return Config(ppn=Decimal("11"), margin=Decimal("3"), state_file=tmp_path / "state.json")


class Sent(list):
    def __call__(self, text):
        self.append(text)


def go(cfg, reseller=RESELLER, sell=SELL_OK):
    sent = Sent()

    def fetch_reseller():
        if isinstance(reseller, Exception):
            raise reseller
        return reseller

    run(cfg, fetch_reseller=fetch_reseller, fetch_sell=lambda: sell, notify=sent)
    return sent


def test_run_pertama_kirim_ringkasan(cfg):
    sent = go(cfg)
    assert len(sent) == 1
    assert "sesuai" in sent[0].lower()


def test_run_kedua_tanpa_perubahan_diam(cfg):
    go(cfg)
    assert go(cfg) == []


def test_harga_rugi_dikirim_sekali_saja(cfg):
    go(cfg)
    sent = go(cfg, sell=SELL_BAD)
    assert len(sent) == 1
    assert "RUGI" in sent[0] and ".web.id" in sent[0]
    assert go(cfg, sell=SELL_BAD) == []


def test_issue_beres_kirim_pemulihan(cfg):
    go(cfg, sell=SELL_BAD)
    sent = go(cfg, sell=SELL_OK)
    assert len(sent) == 1
    assert "sesuai" in sent[0].lower()


def test_perubahan_harga_reseller_dikirim(cfg):
    go(cfg)
    naik = {**RESELLER, "web.id": {"register": 47_000}}
    sent = go(cfg, reseller=naik, sell=SELL_OK)
    text = "\n".join(sent)
    assert "45.000" in text and "47.000" in text
    # harga jual 52.000 → seharusnya 54.000 (47.000 × 1,14 = 53.580)
    assert "54.000" in text


def test_scraper_error_dikirim_sekali_dan_state_reseller_tidak_hilang(cfg):
    go(cfg)
    sent = go(cfg, reseller=ScrapeError("Kolom 'Gold Slab' tidak ditemukan"))
    assert len(sent) == 1 and "Gold Slab" in sent[0]
    assert go(cfg, reseller=ScrapeError("Kolom 'Gold Slab' tidak ditemukan")) == []
    state = json.loads(cfg.state_file.read_text())
    assert state["reseller"] == RESELLER


def test_pulih_dari_error_tanpa_perubahan_harga_kirim_info(cfg):
    go(cfg)
    go(cfg, reseller=ScrapeError("down"))
    sent = go(cfg)
    assert len(sent) == 1
    assert "normal" in sent[0].lower()


MY_RESELLER = {"my.id": {"register": 22_000, "renew": 22_000}}
MY_SELL_PROMO = {"my.id": {"register": 3_000, "renew": 26_000}}


@pytest.fixture
def cfg_promo(tmp_path):
    return Config(
        ppn=Decimal("11"),
        margin=Decimal("3"),
        state_file=tmp_path / "state.json",
        promo=frozenset({("my.id", "register")}),
    )


def test_promo_ditampilkan_terpisah_bukan_rugi(cfg_promo):
    [text] = go(cfg_promo, reseller=MY_RESELLER, sell=MY_SELL_PROMO)
    assert "RUGI" not in text
    assert "sesuai" in text
    assert "🏷️" in text and ".my.id register" in text and "Rp3.000" in text


def test_harga_promo_berubah_tidak_kirim_notif(cfg_promo):
    go(cfg_promo, reseller=MY_RESELLER, sell=MY_SELL_PROMO)
    lima_ribu = {"my.id": {"register": 5_000, "renew": 26_000}}
    assert go(cfg_promo, reseller=MY_RESELLER, sell=lima_ribu) == []


def test_promo_selesai_kirim_pengingat_sekali(cfg_promo):
    go(cfg_promo, reseller=MY_RESELLER, sell=MY_SELL_PROMO)
    normal = {"my.id": {"register": 26_000, "renew": 26_000}}
    [text] = go(cfg_promo, reseller=MY_RESELLER, sell=normal)
    assert "PROMO" in text and ".my.id register" in text
    assert go(cfg_promo, reseller=MY_RESELLER, sell=normal) == []


def test_setiap_run_menulis_log_ringkasan(cfg, caplog):
    caplog.set_level("INFO", logger="pricewatch")
    go(cfg)
    go(cfg)
    summaries = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Cek selesai")]
    assert len(summaries) == 2
    assert "2 TLD" in summaries[0] and "0 masalah" in summaries[0] and "notifikasi dikirim" in summaries[0]
    assert "tidak ada notifikasi" in summaries[1]


def test_log_ringkasan_hitung_masalah_dan_promo(cfg_promo, caplog):
    caplog.set_level("INFO", logger="pricewatch")
    sell = {"my.id": {"register": 3_000, "renew": 25_000}}
    go(cfg_promo, reseller=MY_RESELLER, sell=sell)
    [summary] = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Cek selesai")]
    assert "1 masalah" in summary and "1 promo" in summary
