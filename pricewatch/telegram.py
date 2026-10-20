import requests

MAX_LEN = 4096  # batas panjang pesan Telegram


class TelegramError(Exception):
    pass


def split_lines(text: str, limit: int = MAX_LEN) -> list[str]:
    # Dipecah di batas baris supaya tag HTML seperti <b> tidak terpotong di tengah;
    # pesan yang tagnya terpotong ditolak Telegram dan akan gagal terus di setiap run
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(line) > limit:
            line = line[: limit - 20] + " … (terpotong)"
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            candidate = line
        current = candidate
    chunks.append(current)
    return chunks


def send_message(token: str, chat_id: str, text: str, thread_id: str | None = None, timeout: float = 30) -> None:
    for chunk in split_lines(text):
        _send(token, chat_id, chunk, thread_id, timeout)


def _send(token: str, chat_id: str, text: str, thread_id: str | None, timeout: float) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if thread_id:
        # Tanpa message_thread_id, pesan di grup forum masuk ke topik General
        payload["message_thread_id"] = int(thread_id)
    resp = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=timeout)
    if not resp.ok:
        # raise_for_status() hanya memberi kode HTTP. Alasan dari Telegram, misalnya
        # "message thread not found", ada di field description
        try:
            description = resp.json().get("description", "")
        except ValueError:
            description = ""
        raise TelegramError(f"HTTP {resp.status_code}: {description or 'tanpa deskripsi'}")
