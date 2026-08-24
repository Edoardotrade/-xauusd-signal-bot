"""Ascoltatore comandi Telegram (sistema separato dai motori dei segnali).

Sta in ascolto (long polling su getUpdates) e risponde al comando /analisi
con l'analisi di mercato dell'oro (vedi analisi.py). E' l'UNICO processo che
legge gli aggiornamenti Telegram: i motori dei segnali solo INVIANO, quindi
non c'e' conflitto sul token.

Gira ~5h30m in loop e poi si riavvia (come i motori), oppure parte dal cron.
"""
from __future__ import annotations

import os
import sys
import time

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_API = f"https://api.telegram.org/bot{_TOKEN}"
_MAX_RUNTIME = int(os.getenv("MAX_RUNTIME", str(5 * 3600 + 30 * 60)))  # ~5h30m
_POLL = 25  # secondi di long polling per richiesta


def _send(chat_id: int | str, text: str) -> None:
    try:
        requests.post(f"{_API}/sendMessage", json={
            "chat_id": chat_id, "text": text,
            "parse_mode": "HTML", "disable_web_page_preview": True,
        }, timeout=30)
    except Exception as exc:  # noqa: BLE001
        print(f"[listener] invio fallito: {exc}", file=sys.stderr, flush=True)


def _get_updates(offset: int | None) -> list[dict]:
    params = {"timeout": _POLL}
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(f"{_API}/getUpdates", params=params, timeout=_POLL + 10)
        return r.json().get("result", []) if r.ok else []
    except Exception as exc:  # noqa: BLE001
        print(f"[listener] getUpdates errore: {exc}", file=sys.stderr, flush=True)
        time.sleep(3)
        return []


def _handle(text: str, chat_id: int | str) -> None:
    cmd = text.strip().lower().split("@")[0].split()[0] if text.strip() else ""
    if cmd == "/analisi":
        print(f"[listener] /analisi da {chat_id}", flush=True)
        try:
            from analisi import build_analisi
            _send(chat_id, build_analisi())
        except Exception as exc:  # noqa: BLE001
            _send(chat_id, "⚠️ Non riesco a generare l'analisi ora, riprova tra poco.")
            print(f"[listener] errore analisi: {exc}", file=sys.stderr, flush=True)
    elif cmd in ("/start", "/help"):
        _send(chat_id, "👋 Scrivi <b>/analisi</b> per ricevere l'analisi di mercato dell'oro.")


def main() -> int:
    if not _TOKEN:
        print("[listener] TELEGRAM_BOT_TOKEN mancante", file=sys.stderr)
        return 1
    start = time.time()
    # All'avvio: scarta gli aggiornamenti vecchi (non rispondere a comandi arretrati).
    offset = None
    old = _get_updates(None)
    if old:
        offset = old[-1]["update_id"] + 1
    print(f"[listener] avviato, durata max {_MAX_RUNTIME}s", flush=True)

    while time.time() - start < _MAX_RUNTIME:
        for u in _get_updates(offset):
            offset = u["update_id"] + 1
            msg = u.get("message") or u.get("channel_post") or {}
            text = msg.get("text", "")
            chat = (msg.get("chat") or {}).get("id")
            if text and chat is not None:
                _handle(text, chat)
    print("[listener] fine turno, mi riavvio via workflow", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
