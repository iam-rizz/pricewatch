import pytest

from pricewatch import telegram
from pricewatch.telegram import TelegramError


class FakeResponse:
    def __init__(self, status=200, body=None):
        self.status_code = status
        self.ok = status < 400
        self._body = body or {"ok": True}

    def json(self):
        return self._body


class Posted(list):
    response = None


@pytest.fixture
def posted(monkeypatch):
    calls = Posted()

    def fake_post(url, json, timeout):
        calls.append(json)
        return calls.response or FakeResponse()

    monkeypatch.setattr(telegram.requests, "post", fake_post)
    return calls


def test_kirim_tanpa_topik_tidak_ada_thread_id(posted):
    telegram.send_message("tok", "-1003658699335", "halo")
    assert "message_thread_id" not in posted[0]
    assert posted[0]["chat_id"] == "-1003658699335"


def test_kirim_ke_topik_pakai_message_thread_id(posted):
    telegram.send_message("tok", "-1003658699335", "halo", thread_id="215082")
    assert posted[0]["message_thread_id"] == 215082


def test_error_telegram_tampilkan_deskripsi(posted):
    posted.response = FakeResponse(400, {"ok": False, "description": "Bad Request: message thread not found"})
    with pytest.raises(TelegramError, match="message thread not found"):
        telegram.send_message("tok", "-1003658699335", "halo", thread_id="1")
