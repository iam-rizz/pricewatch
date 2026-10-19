from dataclasses import dataclass
from decimal import Decimal

from pricewatch.pricing import harga_jual, modal

Prices = dict[str, dict[str, int]]


@dataclass(frozen=True)
class Issue:
    kind: str  # "loss" | "mismatch" | "missing"
    tld: str
    action: str | None
    reseller: int
    expected: int
    actual: int | None

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.tld}:{self.action}:{self.reseller}:{self.actual}"


def find_issues(reseller: Prices, sell: Prices, ppn: Decimal, margin: Decimal) -> list[Issue]:
    issues = []
    # Hanya TLD yang ada di digitalregistra (domain Indonesia); TLD lain di WHMCS diabaikan
    for tld in sorted(reseller):
        for action, base in reseller[tld].items():
            expected = harga_jual(base, ppn, margin)
            actual = sell.get(tld, {}).get(action)
            if actual is None:
                kind = "missing"
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
