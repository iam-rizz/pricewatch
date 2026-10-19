import requests

MAX_LEN = 4096  # batas panjang pesan Telegram


def send_message(token: str, chat_id: str, text: str, timeout: float = 30) -> None:
    if len(text) > MAX_LEN:
        text = text[: MAX_LEN - 20] + "\n… (terpotong)"
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=timeout,
    )
    resp.raise_for_status()
