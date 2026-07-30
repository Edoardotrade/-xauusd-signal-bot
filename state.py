"""Guardia anti-doppione persistente.

Ricorda l'ultima barra inviata per ogni timeframe: se lo stesso segnale
(stessa candela) e' gia' stato mandato, non lo re-invia. Rende gli invii
IDEMPOTENTI anche se piu' esecuzioni si sovrappongono (motore + cron manuali).
"""
from __future__ import annotations

import json
import os

STATE_PATH = os.path.join(os.path.dirname(__file__), "sent_state.json")


def _load() -> dict:
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def already_sent(timeframe: str, bar_time: str) -> bool:
    """True se per questo timeframe l'ultima barra inviata e' proprio bar_time."""
    return _load().get(timeframe) == bar_time


def mark_sent(timeframe: str, bar_time: str) -> None:
    data = _load()
    data[timeframe] = bar_time
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
