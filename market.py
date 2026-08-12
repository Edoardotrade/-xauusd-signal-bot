"""Consapevolezza degli orari di mercato per XAUUSD (oro spot).

Il mercato dell'oro (forex/CFD) segue la settimana forex:
  - APRE   domenica ~22:00 UTC
  - CHIUDE venerdi  ~21:00 UTC
  - PAUSA giornaliera di rollover ~21:00-22:00 UTC (bassa liquidita')
  - CHIUSO tutto il sabato

NB: orari APPROSSIMATI. Non gestiscono l'ora legale (DST, +/- 1h in certi
periodi) ne' le festivita'. Servono a evitare invii con dati palesemente
vecchi, non a fare timing di precisione.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    _ROME = ZoneInfo("Europe/Rome")
except Exception:  # tzdata mancante: fallback semplice (UTC+2, estate)
    _ROME = None

# Fascia operativa in ora ITALIANA (configurabile). Trade solo tra le due ore.
_TRADE_START = int(os.getenv("TRADE_START_HOUR", "9"))
_TRADE_END = int(os.getenv("TRADE_END_HOUR", "21"))


def in_trading_window(now: datetime | None = None) -> tuple[bool, str]:
    """True se l'ora italiana e' nella fascia operativa (default 08:00-22:00)."""
    now = now or datetime.now(timezone.utc)
    if _ROME is not None:
        h = now.astimezone(_ROME).hour
    else:
        h = (now.hour + 2) % 24  # fallback ~UTC+2 (estate) se tzdata assente
    if _TRADE_START <= h < _TRADE_END:
        return True, ""
    return False, (f"Fuori orario operativo ({_TRADE_START:02d}:00-{_TRADE_END:02d}:00 "
                   "ora italiana): nessun trade.")


def is_market_open(now: datetime | None = None) -> tuple[bool, str]:
    """Ritorna (aperto?, motivo_se_chiuso) in base all'ora UTC corrente."""
    now = now or datetime.now(timezone.utc)
    wd = now.weekday()  # lun=0 ... sab=5, dom=6
    hour = now.hour

    if wd == 5:
        return False, "Sabato: mercato chiuso."
    if wd == 6 and hour < 22:
        return False, "Domenica: il mercato riapre verso le ~22:00 UTC."
    if wd == 4 and hour >= 21:
        return False, "Venerdi sera: mercato chiuso (~21:00 UTC)."
    if hour == 21:
        return False, "Pausa giornaliera di rollover (~21:00-22:00 UTC)."
    return True, ""
