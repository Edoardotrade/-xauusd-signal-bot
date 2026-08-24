"""Ascoltatore comandi Telegram (sistema separato dai motori dei segnali).

Comandi:
  /analisi            -> analisi di mercato dell'oro (vedi analisi.py)
  /jarvis <messaggio> -> lascia una richiesta a Jarvis (salvata nel repo, la
                         legge quando si accende il PC)
  /note               -> mostra le richieste ancora in sospeso

E' l'UNICO processo che LEGGE gli aggiornamenti Telegram (long polling su
getUpdates): i motori dei segnali solo INVIANO, quindi non c'e' conflitto sul
token. Gira ~5h30m e poi si riavvia (come i motori) oppure parte dal cron.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_API = f"https://api.telegram.org/bot{_TOKEN}"
_MAX_RUNTIME = int(os.getenv("MAX_RUNTIME", str(5 * 3600 + 30 * 60)))  # ~5h30m
_POLL = 25  # secondi di long polling per richiesta
_NOTE_FILE = os.path.join(os.path.dirname(__file__), "richieste_jarvis.md")
_DASH = "—"  # em-dash


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


def _git(*args: str) -> int:
    return subprocess.run(["git", *args], capture_output=True, text=True).returncode


def _save_note(text: str, chat: int | str) -> bool:
    """Aggiunge una richiesta al file e la committa nel repo (persistenza)."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    line = f"- [ ] {ts} (chat {chat}) {_DASH} {text}\n"
    try:
        new = not os.path.exists(_NOTE_FILE)
        with open(_NOTE_FILE, "a", encoding="utf-8") as fh:
            if new:
                fh.write("# Richieste per Jarvis (dal telefono via /jarvis)\n\n")
            fh.write(line)
    except Exception as exc:  # noqa: BLE001
        print(f"[listener] scrittura nota fallita: {exc}", file=sys.stderr, flush=True)
        return False
    _git("config", "user.name", "listener-bot")
    _git("config", "user.email", "bot@users.noreply.github.com")
    _git("add", _NOTE_FILE)
    if _git("diff", "--cached", "--quiet") == 0:
        return True
    for _ in range(6):
        _git("commit", "-m", "nota /jarvis dal telefono")
        _git("pull", "--rebase", "origin", "main")
        if _git("push", "origin", "HEAD:main") == 0:
            return True
        _git("reset", "--soft", "HEAD~1")
        time.sleep(3)
    return True  # salvata localmente comunque


def _pending_notes() -> list[str]:
    if not os.path.exists(_NOTE_FILE):
        return []
    with open(_NOTE_FILE, encoding="utf-8") as fh:
        return [l.strip() for l in fh if l.strip().startswith("- [ ]")]


def _handle(text: str, chat_id: int | str) -> None:
    body = text.strip()
    cmd = body.lower().split("@")[0].split()[0] if body else ""
    if cmd == "/analisi":
        print(f"[listener] /analisi da {chat_id}", flush=True)
        try:
            from analisi import build_analisi
            _send(chat_id, build_analisi())
        except Exception as exc:  # noqa: BLE001
            _send(chat_id, "⚠️ Non riesco a generare l'analisi ora, riprova tra poco.")
            print(f"[listener] errore analisi: {exc}", file=sys.stderr, flush=True)
    elif cmd == "/jarvis":
        nota = body[len("/jarvis"):].strip()
        if not nota:
            _send(chat_id, "✍️ Scrivi il messaggio dopo il comando, es:\n"
                           "<code>/jarvis cambia la fascia a 10-18</code>")
            return
        ok = _save_note(nota, chat_id)
        _send(chat_id, ("✅ <b>Messaggio salvato per Jarvis.</b>\n"
                        "Lo leggo e ci lavoro quando accendi il PC. \U0001f916")
              if ok else "⚠️ Non sono riuscito a salvare la nota, riprova.")
    elif cmd == "/note":
        pend = _pending_notes()
        if not pend:
            _send(chat_id, "\U0001f4ed Nessuna richiesta in sospeso.")
        else:
            _send(chat_id, "\U0001f4cb <b>Richieste in sospeso per Jarvis:</b>\n"
                  + "\n".join(pend[-15:]))
    elif cmd in ("/start", "/help"):
        _send(chat_id, "\U0001f916 <b>Comandi disponibili</b>\n"
              "• <b>/analisi</b> — analisi del mercato oro\n"
              "• <b>/jarvis</b> &lt;messaggio&gt; — lascia una richiesta a Jarvis "
              "(la leggo quando accendi il PC)\n"
              "• <b>/note</b> — vedi le richieste in sospeso")


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
                try:
                    _handle(text, chat)
                except Exception as exc:  # noqa: BLE001
                    print(f"[listener] errore handle: {exc}", file=sys.stderr, flush=True)
    print("[listener] fine turno, mi riavvio via workflow", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
