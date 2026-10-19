import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from pricewatch.main import LocalFormatter, local_tz


def test_local_tz_dari_env(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Jakarta")
    assert datetime(2026, 10, 20, tzinfo=local_tz()).utcoffset() == timedelta(hours=7)


def test_local_tz_default_asia_jakarta(monkeypatch):
    monkeypatch.delenv("TZ", raising=False)
    assert datetime(2026, 10, 20, tzinfo=local_tz()).utcoffset() == timedelta(hours=7)


def test_local_tz_nama_salah_jatuh_ke_utc(monkeypatch):
    monkeypatch.setenv("TZ", "Asia/Tidak_Ada")
    assert local_tz() == timezone.utc


def test_formatter_tulis_jam_wib():
    record = logging.LogRecord("pricewatch", logging.INFO, __file__, 1, "halo", None, None)
    record.created = 1_760_900_000  # 2025-10-19 18:53:20 UTC
    text = LocalFormatter("%(asctime)s %(message)s", tz=ZoneInfo("Asia/Jakarta")).format(record)
    assert text == "2025-10-20 01:53:20 WIB halo"
