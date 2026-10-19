from decimal import Decimal

from pricewatch.check import find_issues, reseller_changes

PPN = Decimal("11")
MARGIN = Decimal("3")


def test_harga_sesuai_tidak_ada_issue():
    reseller = {"web.id": {"register": 45_000, "renew": 45_000}}
    sell = {"web.id": {"register": 52_000, "renew": 52_000}}
    assert find_issues(reseller, sell, PPN, MARGIN) == []


def test_harga_jual_terlalu_mahal_jadi_mismatch():
    reseller = {"web.id": {"register": 45_000}}
    sell = {"web.id": {"register": 55_000}}
    [issue] = find_issues(reseller, sell, PPN, MARGIN)
    assert issue.kind == "mismatch"
    assert (issue.tld, issue.action, issue.expected, issue.actual) == ("web.id", "register", 52_000, 55_000)


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
