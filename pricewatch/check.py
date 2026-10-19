from dataclasses import dataclass
from decimal import Decimal

from pricewatch.pricing import harga_jual, modal

Prices = dict[str, dict[str, int]]
Promo = frozenset[tuple[str, str]]

INFO_KINDS = frozenset({"promo", "promo_ended"})


@dataclass(frozen=True)
class Issue:
    kind: str  # "loss" | "mismatch" | "missing" | "promo" | "promo_ended"
    tld: str
    action: str | None
    reseller: int
    expected: int
    actual: int | None

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
    reseller: Prices, sell: Prices, ppn: Decimal, margin: Decimal, promo: Promo = frozenset()
) -> list[Issue]:
    issues = []
    # Daftar TLD diambil dari tabel digitalregistra, jadi TLD lain di WHMCS (.com dan seterusnya) tidak dicek
    for tld in sorted(reseller):
        for action, base in reseller[tld].items():
            expected = harga_jual(base, ppn, margin)
            actual = sell.get(tld, {}).get(action)
            if actual is None:
                kind = "missing"
            elif (tld, action) in promo and actual <= expected:
                # Di bawah rumus berarti promo masih jalan; sama dengan rumus berarti promo sudah selesai
                kind = "promo" if actual < expected else "promo_ended"
            elif actual < modal(base, ppn):
                kind = "loss"
            elif actual != expected:
                kind = "mismatch"
            else:
                continue
            issues.append(Issue(kind, tld, action, base, expected, actual))
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
