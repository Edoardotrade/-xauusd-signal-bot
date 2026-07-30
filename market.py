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

from datetime import datetime, timezone


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
