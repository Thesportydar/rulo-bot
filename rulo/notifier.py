from __future__ import annotations

import os
import sys
import urllib.parse
import urllib.request
from typing import Protocol


class Notifier(Protocol):
    def send(self, message: str) -> bool: ...


class ConsoleNotifier:
    def send(self, message: str) -> bool:
        print(message)
        return True


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.url = f"https://api.telegram.org/bot{token}/sendMessage"
        self.chat_id = chat_id

    def send(self, message: str) -> bool:
        data = urllib.parse.urlencode(
            {"chat_id": self.chat_id, "text": message, "parse_mode": "HTML", "disable_web_page_preview": "true"}
        ).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(self.url, data=data), timeout=15) as resp:
                return resp.status == 200
        except Exception as e:  # noqa: BLE001 - un fallo de red no debe tirar el monitor
            print(f"telegram: error enviando mensaje: {e}", file=sys.stderr)
            return False


def _telegram_token() -> str | None:
    if token := os.environ.get("TELEGRAM_BOT_TOKEN"):
        return token
    if param := os.environ.get("TELEGRAM_BOT_TOKEN_PARAM"):
        import boto3

        return boto3.client("ssm").get_parameter(Name=param, WithDecryption=True)["Parameter"]["Value"]
    return None


def build_notifier(cfg: dict) -> Notifier:
    token, chat_id = _telegram_token(), os.environ.get("TELEGRAM_CHAT_ID")
    if cfg.get("telegram", {}).get("enabled", True) and token and chat_id:
        return TelegramNotifier(token, chat_id)
    print("telegram: sin token o TELEGRAM_CHAT_ID, uso consola", file=sys.stderr)
    return ConsoleNotifier()
