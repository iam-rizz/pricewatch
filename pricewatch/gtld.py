from decimal import Decimal, InvalidOperation

import requests
from bs4 import BeautifulSoup

from pricewatch.registra import USER_AGENT, ScrapeError

URL = "https://www.digitalregistra.co.id/harga-gtld/"
HEADERS = ("ekstensi domain", "persyaratan", "harga register", "renewal", "transfer")
# Kolom harga di tabel: 2 = register, 3 = renewal, 4 = transfer
COLUMNS = {"register": 2, "renew": 3, "transfer": 4}

UsdPrices = dict[str, dict[str, Decimal]]


def fetch_html(timeout: float = 30) -> str:
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _usd(cell, tld: str) -> Decimal:
    # Register yang sedang promo ditulis <del>harga normal</del> harga promo; yang dipakai harga promo
    for old in cell.find_all("del"):
        old.decompose()
    text = cell.get_text(strip=True).replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ScrapeError(f"Harga .{tld} tidak bisa dibaca: '{text}'") from None


def parse_gtld(html: str) -> UsdPrices:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tabeldomain")
    if table is None:
        raise ScrapeError("Tabel harga gTLD (id=tabeldomain) tidak ditemukan")

    headers = tuple(th.get_text(strip=True).lower() for th in table.find_all("th"))[: len(HEADERS)]
    if headers != HEADERS:
        raise ScrapeError(f"Header tabel gTLD berubah: {list(headers)}")

    prices: UsdPrices = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) <= max(COLUMNS.values()):
            continue
        tld = cells[0].get_text(strip=True).lstrip(".").lower()
        prices[tld] = {action: _usd(cells[i], tld) for action, i in COLUMNS.items()}

    if not prices:
        raise ScrapeError("Tidak ada harga gTLD yang terbaca")
    return prices
