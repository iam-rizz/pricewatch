from decimal import ROUND_CEILING, Decimal

ROUND_TO = Decimal(1000)
HUNDRED = Decimal(100)


def harga_jual(reseller: int, ppn_percent: Decimal, margin_percent: Decimal) -> int:
    # Sama dengan Excel =ROUNDUP(reseller*(1+ppn+margin), -3). Pakai Decimal karena di float
    # 1 + 0.11 + 0.03 = 1.1400000000000001, sehingga reseller 200.000 dibulatkan ke 229.000
    raw = Decimal(reseller) * (1 + (ppn_percent + margin_percent) / HUNDRED)
    return int((raw / ROUND_TO).to_integral_value(rounding=ROUND_CEILING) * ROUND_TO)


def modal(reseller: int, ppn_percent: Decimal) -> Decimal:
    return Decimal(reseller) * (1 + ppn_percent / HUNDRED)
