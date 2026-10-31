from decimal import Decimal

from pricewatch.check import find_issues, reseller_changes

PPN = Decimal("11")
MARGIN = Decimal("3")


def test_harga_sesuai_tidak_ada_issue():
    reseller = {"web.id": {"register": 45_000, "renew": 45_000}}
    sell = {"web.id": {"register": 52_000, "renew": 52_000}}
    assert find_issues(reseller, sell, PPN, MARGIN) == []


def test_harga_jual_di_atas_rumus_tidak_dilaporkan():
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 55_000}}
    assert find_issues(reseller, sell, PPN, MARGIN) == []


def test_harga_jual_di_bawah_rumus_jadi_mismatch():
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 51_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN)
    assert issue.kind == "mismatch"
    assert (issue.tld, issue.action, issue.expected, issue.actual) == ("web.id", "register", 52_000, 51_000)


def test_gtld_di_atas_rumus_tidak_dilaporkan():
    reseller = {"com": {"renew": Decimal("11.75")}}
    sell = {"com": {"renew": 260_000}}
    assert find_issues(reseller, sell, PPN, MARGIN, to_idr=lambda usd: usd * 18_500, round_to=500) == []


def test_harga_jual_di_bawah_modal_jadi_rugi():
    # modal 45.000 + PPN = 49.950; dijual 49.000 → rugi
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 49_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN)
    assert issue.kind == "loss"


def test_harga_kurang_tapi_masih_di_atas_modal_tetap_mismatch():
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 50_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN)
    assert issue.kind == "mismatch"


def test_tld_tidak_dijual_di_whmcs():
    reseller = {"ponpes.id": {"register": 45_000}}
    [issue] = find_issues(reseller, {}, PPN, MARGIN)
    assert issue.kind == "missing"
    assert issue.tld == "ponpes.id"


def test_action_tidak_dijual_di_whmcs():
    reseller = {"web.id": {"register": 45_000, "transfer": 45_000}}
    sell = {"web.id": {"register": 52_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN)
    assert (issue.kind, issue.action) == ("missing", "transfer")


def test_tld_whmcs_non_indonesia_diabaikan():
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 52_000}, "com": {"register": 1}}
    assert find_issues(reseller, sell, PPN, MARGIN) == []


def test_fingerprint_issue_stabil():
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 55_000}}
    a = find_issues(reseller, sell, PPN, MARGIN)
    b = find_issues(reseller, sell, PPN, MARGIN)
    assert [i.key for i in a] == [i.key for i in b]


def test_reseller_changes_deteksi_naik_turun_baru_hilang():
    old = {"web.id": {"register": 45_000}, "or.id": {"register": 45_000}, "sch.id": {"register": 45_000}}
    new = {"web.id": {"register": 47_000}, "or.id": {"register": 45_000}, "my.id": {"register": 22_000}}
    changes = reseller_changes(old, new)
    assert ("web.id", "register", 45_000, 47_000) in changes
    assert ("my.id", "register", None, 22_000) in changes
    assert ("sch.id", "register", 45_000, None) in changes
    assert len(changes) == 3


def test_reseller_changes_run_pertama_kosong():
    assert reseller_changes(None, {"web.id": {"register": 45_000}}) == []


PROMO = frozenset({("my.id", "register")})


def test_promo_di_bawah_rumus_bukan_rugi():
    reseller = {"my.id": {"register": 22_000}}
    sell = {"my.id": {"register": 3_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN, promo=PROMO)
    assert issue.kind == "promo"


def test_promo_kembali_ke_harga_rumus_jadi_promo_ended():
    reseller = {"my.id": {"register": 22_000}}
    sell = {"my.id": {"register": 26_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN, promo=PROMO)
    assert issue.kind == "promo_ended"


def test_promo_di_atas_rumus_jadi_promo_ended():
    # Harga sudah tidak di bawah rumus, jadi promo dianggap selesai dan perlu dihapus dari PROMO
    reseller = {"my.id": {"register": 22_000}}
    sell = {"my.id": {"register": 30_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN, promo=PROMO)
    assert issue.kind == "promo_ended"


def test_promo_hanya_berlaku_untuk_aksi_yang_disebut():
    reseller = {"my.id": {"register": 22_000, "renew": 22_000}}
    sell = {"my.id": {"register": 3_000, "renew": 3_000}}
    kinds = {i.action: i.kind for i in find_issues(reseller, sell, PPN, MARGIN, promo=PROMO)}
    assert kinds == {"register": "promo", "renew": "loss"}


def test_promo_tidak_dijual_tetap_missing():
    reseller = {"my.id": {"register": 22_000}}
    [issue] = find_issues(reseller, {}, PPN, MARGIN, promo=PROMO)
    assert issue.kind == "missing"


def test_key_promo_tidak_berubah_saat_harga_promo_berubah():
    reseller = {"my.id": {"register": 22_000}}
    [a] = find_issues(reseller, {"my.id": {"register": 3_000}}, PPN, MARGIN, promo=PROMO)
    [b] = find_issues(reseller, {"my.id": {"register": 5_000}}, PPN, MARGIN, promo=PROMO)
    assert a.key == b.key


def usd_to_idr(kurs):
    return lambda usd: usd * kurs


def test_gtld_dikonversi_dengan_kurs_dan_dibulatkan_500():
    reseller = {"top": {"renew": Decimal("6.35")}}
    sell = {"top": {"renew": 130_500}}
    assert find_issues(reseller, sell, PPN, MARGIN, to_idr=usd_to_idr(18_000), round_to=500) == []


def test_gtld_mismatch_menyimpan_harga_usd_dan_modal_rupiah():
    # modal 11,75 × 18.500 × 1,11 = 241.286,25; dijual 245.000 → di atas modal tapi di bawah rumus
    reseller = {"com": {"renew": Decimal("11.75")}}
    sell = {"com": {"renew": 245_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN, to_idr=usd_to_idr(18_500), round_to=500)
    assert issue.kind == "mismatch"
    assert issue.reseller == Decimal("11.75")
    assert issue.expected == 248_000  # 11,75 × 18.500 × 1,14 = 247.807,5 → 248.000
    assert issue.cost == Decimal("11.75") * 18_500 * Decimal("1.11")


def test_gtld_key_tetap_saat_kurs_berubah():
    reseller = {"com": {"renew": Decimal("11.75")}}
    sell = {"com": {"renew": 240_500}}
    [a] = find_issues(reseller, sell, PPN, MARGIN, to_idr=usd_to_idr(18_500), round_to=500)
    [b] = find_issues(reseller, sell, PPN, MARGIN, to_idr=usd_to_idr(19_000), round_to=500)
    assert a.key == b.key


def test_only_sold_lewati_tld_yang_tidak_dijual():
    reseller = {"com": {"renew": Decimal("11.75")}, "zone": {"renew": Decimal("33.34")}}
    sell = {"com": {"renew": 248_000}}
    assert find_issues(reseller, sell, PPN, MARGIN, to_idr=usd_to_idr(18_500), round_to=500, only_sold=True) == []


def test_only_sold_tetap_lapor_aksi_yang_tidak_dijual():
    reseller = {"com": {"register": Decimal("11.75"), "transfer": Decimal("11.75")}}
    sell = {"com": {"register": 248_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN, to_idr=usd_to_idr(18_500), round_to=500, only_sold=True)
    assert (issue.kind, issue.action) == ("missing", "transfer")


def test_gtld_modal_pakai_kurs_live_bukan_kurs_efektif():
    # Harga seharusnya pakai kurs efektif 18.500: 11,75 × 18.500 × 1,14 → 248.000.
    # Modal pakai kurs live 18.055: 11,75 × 18.055 × 1,11 = 235.487 → 240.500 bukan rugi
    reseller = {"com": {"renew": Decimal("11.75")}}
    sell = {"com": {"renew": 240_500}}
    [issue] = find_issues(
        reseller, sell, PPN, MARGIN,
        to_idr=usd_to_idr(18_500), cost_to_idr=usd_to_idr(Decimal("18055")), round_to=500,
    )
    assert issue.kind == "mismatch"
    assert issue.expected == 248_000
    assert issue.cost == Decimal("11.75") * Decimal("18055") * Decimal("1.11")
