from decimal import Decimal

from pricewatch.check import Issue
from pricewatch.main import format_issues


def issue(kind, tld, action, actual, expected=252_000, cost=Decimal("238000")):
    return Issue(kind, tld, action, Decimal("11.93"), expected, actual, cost)


def test_aksi_dengan_harga_sama_digabung_satu_baris():
    text = format_issues([issue("mismatch", "net", a, 245_000) for a in ("register", "renew", "transfer")])
    assert "🟡 .net register, renew, transfer: jual Rp245.000, seharusnya Rp252.000" in text
    assert text.count(".net") == 1


def test_judul_menghitung_baris_setelah_digabung():
    text = format_issues([issue("mismatch", "net", a, 245_000) for a in ("register", "renew")])
    assert "perlu dicek (1)" in text


def test_harga_berbeda_tidak_digabung():
    text = format_issues(
        [issue("mismatch", "org", "register", 186_000, 191_000), issue("mismatch", "org", "renew", 240_000)]
    )
    assert text.count(".org") == 2


def test_jenis_berbeda_tidak_digabung():
    text = format_issues([issue("loss", "work", "register", 139_000), issue("mismatch", "work", "renew", 245_000)])
    assert "🔴 <b>RUGI</b> .work register" in text and "🟡 .work renew" in text


def test_urutan_aksi_tetap_register_renew_transfer():
    text = format_issues([issue("mismatch", "top", a, 130_500) for a in ("transfer", "register", "renew")])
    assert ".top register, renew, transfer:" in text


def test_rugi_dengan_modal_berbeda_tidak_digabung():
    a = issue("loss", "biz", "register", 380_000, cost=Decimal("384000"))
    b = issue("loss", "biz", "renew", 380_000, cost=Decimal("390000"))
    text = format_issues([a, b])
    assert "modal Rp384.000" in text and "modal Rp390.000" in text
