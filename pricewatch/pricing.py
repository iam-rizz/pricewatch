from decimal import ROUND_CEILING, Decimal

ROUND_TO = Decimal(1000)
HUNDRED = Decimal(100)


def harga_jual(reseller: int, ppn_percent: Decimal, margin_percent: Decimal) -> int:
    # Mirrors Excel =ROUNDUP(reseller*(1+ppn+margin), -3). Decimal avoids float drift
    # (in float 1 + 0.11 + 0.03 = 1.1400000000000001, so 200000 would round up to 229000).
    raw = Decimal(reseller) * (1 + (ppn_percent + margin_percent) / HUNDRED)
    return int((raw / ROUND_TO).to_integral_value(rounding=ROUND_CEILING) * ROUND_TO)


def modal(reseller: int, ppn_percent: Decimal) -> Decimal:
    return Decimal(reseller) * (1 + ppn_percent / HUNDRED)
