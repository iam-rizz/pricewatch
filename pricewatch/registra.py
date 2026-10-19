import requests
from bs4 import BeautifulSoup

URL = "https://www.digitalregistra.co.id/harga-domain-indonesia/"
SLAB = "Gold Slab"
ACTIONS = ("register", "renew", "transfer")
USER_AGENT = "Mozilla/5.0 (compatible; pricewatch/1.0)"


class ScrapeError(Exception):
    pass


def fetch_html(timeout: float = 30) -> str:
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def _to_int(text: str) -> int:
    # "270.000" → 270000 (titik = pemisah ribuan)
    return int(text.strip().replace(".", "").replace(",", ""))


def parse_gold_slab(html: str) -> dict[str, dict[str, int]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="tabeldomain")
    if table is None:
        raise ScrapeError("Tabel harga (class=tabeldomain) tidak ditemukan")

    rows = table.find_all("tr")
    if len(rows) < 3:
        raise ScrapeError("Struktur tabel harga berubah: jumlah baris header kurang")

    # Baris header pertama berisi "Ekstensi" (rowspan 2), lalu tiap slab dengan colspan 3.
    # Dari colspan itu dihitung kolom tempat slab Gold dimulai
    col = 1
    gold_start = None
    for th in rows[0].find_all("th")[1:]:
        if SLAB.lower() in th.get_text(" ", strip=True).lower():
            gold_start = col
            break
        col += int(th.get("colspan", 1))
    if gold_start is None:
        raise ScrapeError(f"Kolom '{SLAB}' tidak ditemukan di header tabel")

    sub = [th.get_text(strip=True).lower() for th in rows[1].find_all("th")]
    sub_for_gold = sub[gold_start - 1 : gold_start - 1 + len(ACTIONS)]
    if tuple(sub_for_gold) != ACTIONS:
        raise ScrapeError(f"Sub-header {SLAB} berubah: {sub_for_gold}")

    prices: dict[str, dict[str, int]] = {}
    for tr in rows[2:]:
        cells = tr.find_all("td")
        name = cells[0].get_text(strip=True) if cells else ""
        if not name.startswith("."):
            continue  # baris non-TLD seperti Deposit/Transaksi
        values = cells[gold_start : gold_start + len(ACTIONS)]
        if len(values) != len(ACTIONS):
            raise ScrapeError(f"Jumlah kolom di baris {name} kurang")
        try:
            prices[name.lstrip(".").lower()] = {
                action: _to_int(td.get_text()) for action, td in zip(ACTIONS, values)
            }
        except ValueError as e:
            raise ScrapeError(f"Harga {name} tidak bisa dibaca: {e}") from e

    if not prices:
        raise ScrapeError("Tidak ada harga TLD yang terbaca")
    return prices
