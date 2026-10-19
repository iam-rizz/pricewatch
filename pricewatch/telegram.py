import requests

MAX_LEN = 4096  # batas panjang pesan Telegram


class TelegramError(Exception):
    pass


def send_message(token: str, chat_id: str, text: str, thread_id: str | None = None, timeout: float = 30) -> None:
    if len(text) > MAX_LEN:
        text = text[: MAX_LEN - 20] + "\n… (terpotong)"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if thread_id:
        # Grup forum: kirim ke topik tertentu, bukan ke General
        payload["message_thread_id"] = int(thread_id)
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=timeout)
    if not resp.ok:
        # raise_for_status() menyembunyikan alasan Telegram (mis. "message thread not found")
        try:
            description = resp.json().get("description", "")
        except ValueError:
            description = ""
        raise TelegramError(f"HTTP {resp.status_code}: {description or 'tanpa deskripsi'}")
