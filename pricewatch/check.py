from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from pricewatch.pricing import ROUND_TO, harga_jual, modal

# Harga reseller: Rupiah (int) untuk domain .id, USD (Decimal) untuk gTLD
Prices = dict[str, dict[str, int | Decimal]]
Promo = frozenset[tuple[str, str]]

INFO_KINDS = frozenset({"promo", "promo_ended"})


@dataclass(frozen=True)
class Issue:
    kind: str  # "loss" | "mismatch" | "missing" | "promo" | "promo_ended"
    tld: str
    action: str | None
    reseller: int | Decimal  # dalam mata uang reseller, supaya key tidak berubah saat kurs berubah
    expected: int
    actual: int | None
    cost: Decimal  # modal dalam Rupiah: reseller + PPN

    @property
    def key(self) -> str:
        if self.kind in INFO_KINDS:
            # Harga promo boleh naik-turun tanpa memicu notifikasi baru
            return f"{self.kind}:{self.tld}:{self.action}"
        return f"{self.kind}:{self.tld}:{self.action}:{self.reseller}:{self.actual}"

    @property
    def is_alert(self) -> bool:
        return self.kind not in INFO_KINDS


def find_issues(
    reseller: Prices,
    sell: Prices,
    ppn: Decimal,
    margin: Decimal,
    promo: Promo = frozenset(),
    to_idr: Callable[[int | Decimal], int | Decimal] = lambda price: price,
    cost_to_idr: Callable[[int | Decimal], int | Decimal] | None = None,
    round_to: int = ROUND_TO,
    only_sold: bool = False,
) -> list[Issue]:
    # Harga seharusnya boleh memakai kurs yang sudah diberi bantalan (to_idr), tapi modal harus
    # memakai kurs sebenarnya (cost_to_idr); kalau tidak, harga yang masih untung ikut dianggap rugi
    cost_to_idr = cost_to_idr or to_idr
    issues = []
    # Daftar TLD diambil dari tabel digitalregistra, jadi TLD WHMCS yang tidak ada di tabel tidak dicek.
    # only_sold untuk tabel gTLD: ratusan TLD yang tidak Anda jual tidak perlu dilaporkan
    for tld in sorted(reseller):
        if only_sold and tld not in sell:
            continue
        for action, base in reseller[tld].items():
            expected = harga_jual(to_idr(base), ppn, margin, round_to=round_to)
            cost = modal(cost_to_idr(base), ppn)
            actual = sell.get(tld, {}).get(action)
            if actual is None:
                kind = "missing"
            elif (tld, action) in promo:
                # Di bawah rumus berarti promo masih jalan; sama atau di atas rumus berarti promo sudah selesai
                kind = "promo" if actual < expected else "promo_ended"
            elif actual < cost:
                kind = "loss"
            elif actual < expected:
                # Harga di atas rumus disengaja (margin lebih besar), jadi hanya harga di bawah rumus yang dilaporkan
                kind = "mismatch"
            else:
                continue
            issues.append(Issue(kind, tld, action, base, expected, actual, cost))
    return issues


def reseller_changes(old: Prices | None, new: Prices) -> list[tuple[str, str, int | None, int | None]]:
    if not old:
        return []
    changes = []
    for tld in sorted(set(old) | set(new)):
        before, after = old.get(tld, {}), new.get(tld, {})
        for action in sorted(set(before) | set(after)):
            if before.get(action) != after.get(action):
                changes.append((tld, action, before.get(action), after.get(action)))
    return changes
