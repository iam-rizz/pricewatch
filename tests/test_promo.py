import pytest

from pricewatch.main import parse_promo


def test_parse_promo_normalisasi():
    assert parse_promo(" .My.ID:register , biz.id:Register ") == frozenset(
        {("my.id", "register"), ("biz.id", "register")}
    )


def test_parse_promo_kosong():
    assert parse_promo("") == frozenset()
    assert parse_promo(None) == frozenset()


@pytest.mark.parametrize("value", ["my.id", "my.id:daftar", ":register", "my.id:register:1"])
def test_parse_promo_format_salah(value):
    with pytest.raises(ValueError):
        parse_promo(value)
