"""Motore di scheduling always-on.

Un unico processo che gira in continuo e fa scattare i controlli al minuto
ESATTO, senza dipendere dai ritardi del cron di GitHub. Gira ~5h30m poi esce;
il workflow lo riavvia (con handoff continuo), coprendo le 24h.

- 15M: ai minuti :00 :15 :30 :45
- 1H : al minuto :00
- 4H : alle ore 0,4,8,12,16,20 (minuto :00)
- Daily: alle 06:00 UTC
Gli invii sono idempotenti (state.py) e rispettano gli orari di mercato (main.run).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from main import run

MAX_RUNTIME = int(os.getenv("ENGINE_MAX_SECONDS", str(5 * 3600 + 30 * 60)))  # 5h30m
POLL = 20  # secondi tra un controllo e l'altro


def due(now: datetime) -> list[tuple[str, bool]]:
    """Timeframe da eseguire in questo minuto: (interval, only_signals)."""
    jobs: list[tuple[str, bool]] = []
    m, h = now.minute, now.hour
    if m % 15 == 0:
        jobs.append(("15m", True))
    if m == 0:
        jobs.append(("1h", True))
        if h % 4 == 0:
            jobs.append(("4h", True))
        if h == 6:
            jobs.append(("1d", False))  # il Daily invia sempre (anche NO-TRADE)
    return jobs


def _git(*args: str) -> int:
    return subprocess.run(["git", *args], capture_output=True, text=True).returncode


def persist() -> None:
    """Salva log + stato nel repo (se cambiati)."""
    _git("add", "signals_log.csv", "sent_state.json")
    if _git("diff", "--cached", "--quiet") != 0:  # ci sono modifiche
        _git("commit", "-m", "log/stato: aggiornamento (engine)")
        _git("pull", "--rebase", "origin", "main")
        _git("push", "origin", "HEAD:main")


def main() -> int:
    start = time.time()
    fired: set[str] = set()
    print(f"[engine] avviato, durata max {MAX_RUNTIME}s", flush=True)
    while time.time() - start < MAX_RUNTIME:
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y-%m-%d %H:%M")
        for interval, only in due(now):
            key = f"{interval}-{minute_key}"
            if key in fired:
                continue
            fired.add(key)
            try:
                print(f"[engine] {minute_key} -> {interval}", flush=True)
                run(interval=interval, only_signals=only)
                persist()
            except Exception as exc:  # noqa: BLE001 - un timeframe ko non ferma il motore
                print(f"[engine] errore su {interval}: {exc}", file=sys.stderr, flush=True)
        time.sleep(POLL)
    print("[engine] terminato (riavvio schedulato).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
