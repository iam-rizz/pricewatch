from decimal import Decimal

from pricewatch.pricing import harga_jual, modal

PPN = Decimal("11")
MARGIN = Decimal("3")


def test_harga_jual_bulat_pas_ribuan_tidak_naik():
    # 200.000 × 1,14 = 228.000 tepat → Excel ROUNDUP tetap 228.000
    assert harga_jual(200_000, PPN, MARGIN) == 228_000


def test_harga_jual_tidak_kena_float_drift():
    # float: 50000 * (1 + 0.11 + 0.03) = 57000.00000000001 → ceil jadi 58.000
    assert harga_jual(50_000, PPN, MARGIN) == 57_000


def test_harga_jual_dibulatkan_ke_atas_ribuan():
    # 45.000 × 1,14 = 51.300 → 52.000
    assert harga_jual(45_000, PPN, MARGIN) == 52_000
    # 22.000 × 1,14 = 25.080 → 26.000
    assert harga_jual(22_000, PPN, MARGIN) == 26_000


def test_harga_jual_nilai_tabel_registra():
    assert harga_jual(270_000, PPN, MARGIN) == 308_000  # 307.800
    assert harga_jual(210_000, PPN, MARGIN) == 240_000  # 239.400
    assert harga_jual(55_000, PPN, MARGIN) == 63_000    # 62.700


def test_harga_jual_ppn_bisa_diganti():
    # PPN 12% → 100.000 × 1,15 = 115.000
    assert harga_jual(100_000, Decimal("12"), MARGIN) == 115_000


def test_modal_termasuk_ppn_tanpa_pembulatan():
    assert modal(45_000, PPN) == Decimal("49950")


def test_harga_jual_gtld_dibulatkan_ke_atas_500():
    # .top USD 6,35 × kurs 18.000 = 114.300 → × 1,14 = 130.302 → 130.500
    base = Decimal("6.35") * 18_000
    assert harga_jual(base, PPN, MARGIN, round_to=500) == 130_500


def test_harga_jual_gtld_pas_kelipatan_500_tidak_naik():
    # .net USD 11,93 × 18.000 × 1,14 = 244.803,6 → 245.000; 245.000 sendiri tidak naik lagi
    assert harga_jual(Decimal("11.93") * 18_000, PPN, MARGIN, round_to=500) == 245_000
    assert harga_jual(Decimal("250000") / Decimal("1.14"), PPN, MARGIN, round_to=500) == 250_000
