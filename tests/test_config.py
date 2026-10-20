import pytest

from pricewatch.main import Config

REQUIRED = {
    "WHMCS_API_URL": "https://x/includes/api.php",
    "WHMCS_IDENTIFIER": "id",
    "WHMCS_SECRET": "secret",
    "TELEGRAM_BOT_TOKEN": "tok",
    "TELEGRAM_CHAT_ID": "-100",
}


@pytest.fixture
def env(monkeypatch):
    for name in ("GTLD_ENABLED", "GTLD_ROUND_TO", "USD_RATE_ROUND_TO", "PROMO"):
        monkeypatch.delenv(name, raising=False)
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_gtld_default_aktif_harga_bulat_500_kurs_bulat_100(env):
    cfg = Config.from_env()
    assert (cfg.gtld_enabled, cfg.gtld_round_to, cfg.usd_rate_round_to) == (True, 500, 100)


def test_default_dataclass_sama_dengan_default_env():
    from decimal import Decimal
    from pathlib import Path

    assert Config(ppn=Decimal("11"), margin=Decimal("3"), state_file=Path("x")).usd_rate_round_to == 100


@pytest.mark.parametrize("value", ["false", "0", "off", "NO"])
def test_gtld_bisa_dimatikan(env, value):
    env.setenv("GTLD_ENABLED", value)
    assert Config.from_env().gtld_enabled is False


def test_pembulatan_bisa_diubah(env):
    env.setenv("GTLD_ROUND_TO", "1000")
    env.setenv("USD_RATE_ROUND_TO", "100")
    cfg = Config.from_env()
    assert (cfg.gtld_round_to, cfg.usd_rate_round_to) == (1000, 100)


@pytest.mark.parametrize("name", ["GTLD_ROUND_TO", "USD_RATE_ROUND_TO"])
@pytest.mark.parametrize("value", ["0", "-500", "lima ratus"])
def test_pembulatan_tidak_valid_berhenti_dengan_pesan(env, name, value):
    env.setenv(name, value)
    with pytest.raises(SystemExit, match=name):
        Config.from_env()
