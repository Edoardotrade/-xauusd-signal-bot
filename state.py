"""Guardia anti-doppione persistente.

Ricorda l'ultima barra inviata per ogni timeframe: se lo stesso segnale
(stessa candela) e' gia' stato mandato, non lo re-invia. Rende gli invii
IDEMPOTENTI anche se piu' esecuzioni si sovrappongono (motore + cron manuali).
"""
from __future__ import annotations

import json
import os

# Profilo (vuoto = bot 1). Ogni profilo ha il suo file di stato, cosi' due bot
# nello stesso repo non si sovrascrivono la guardia anti-doppione.
_PROFILE = os.getenv("PROFILE", "").strip()
_SUFFIX = f"_{_PROFILE}" if _PROFILE else ""
STATE_PATH = os.path.join(os.path.dirname(__file__), f"sent_state{_SUFFIX}.json")


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


def day_count(timeframe: str, date: str) -> int:
    """Quanti segnali LONG/SHORT gia' inviati per questo timeframe in questa data."""
    return _load().get("_count", {}).get(f"{timeframe}|{date}", 0)


def day_incr(timeframe: str, date: str) -> None:
    data = _load()
    counts = data.get("_count", {})
    counts[f"{timeframe}|{date}"] = counts.get(f"{timeframe}|{date}", 0) + 1
    # Tiene solo gli ultimi ~40 contatori (bounded).
    if len(counts) > 40:
        for k in list(counts)[:-40]:
            del counts[k]
    data["_count"] = counts
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def news_seen(key: str) -> bool:
    """True se questo avviso-evento e' gia' stato inviato."""
    return key in _load().get("_news_seen", [])


def news_mark(key: str) -> None:
    data = _load()
    lst = data.get("_news_seen", [])
    if key not in lst:
        lst.append(key)
    data["_news_seen"] = lst[-300:]  # tiene gli ultimi 300 (limita la dimensione)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
