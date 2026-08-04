"""Esecutore automatico su conto DEMO OANDA (ambiente 'practice').

SICUREZZA: questo modulo parla SOLO con l'endpoint demo di OANDA
(api-fxpractice.oanda.com). Non esegue e non deve MAI eseguire su conti reali.
Nessun trade con soldi veri.

Serve OANDA_API_TOKEN e OANDA_ACCOUNT_ID (dai secrets del workflow).
Modello: UNA posizione alla volta per conto (come nel trading reale su un
account a compensazione). Se c'è già una posizione aperta, il nuovo segnale
viene saltato.
"""
from __future__ import annotations

import os

import requests

# --- SOLO DEMO: endpoint practice fisso. Non modificare verso il conto reale. ---
_BASE = "https://api-fxpractice.oanda.com"
_INSTRUMENT = "XAU_USD"
_TIMEOUT = 20


def enabled() -> bool:
    """True se sono configurati token e account demo."""
    return bool(os.getenv("OANDA_API_TOKEN") and os.getenv("OANDA_ACCOUNT_ID"))


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('OANDA_API_TOKEN', '')}",
        "Content-Type": "application/json",
    }


def _account_url(path: str) -> str:
    acc = os.getenv("OANDA_ACCOUNT_ID", "")
    return f"{_BASE}/v3/accounts/{acc}{path}"


def summary() -> dict | None:
    """Riepilogo conto demo: saldo e numero posizioni aperte."""
    try:
        r = requests.get(_account_url("/summary"), headers=_headers(), timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json().get("account", {})
    except Exception as exc:  # noqa: BLE001
        print(f"[broker] errore summary: {exc}")
        return None


def has_open_position(acc: dict | None = None) -> bool:
    acc = acc if acc is not None else summary()
    if not acc:
        return True  # in dubbio, NON apre (prudente)
    return int(acc.get("openPositionCount", 0)) > 0


def execute_if_flat(direction: str, entry: float, sl: float, tp: float,
                    risk_perc: float) -> str:
    """Apre un ordine a mercato sul demo se non c'è già una posizione.
    Size = rischio risk_perc% del saldo demo reale, in base alla distanza dallo SL.
    """
    acc = summary()
    if acc is None:
        return "no-account"
    if has_open_position(acc):
        return "posizione-gia-aperta"

    balance = float(acc.get("balance", 0) or 0)
    sl_dist = abs(entry - sl)
    if balance <= 0 or sl_dist <= 0:
        return "dati-non-validi"

    # XAU_USD: 1 unità = 1 oncia, P/L ~ 1$ per unità per ogni 1$ di movimento.
    units = max(1, round(balance * risk_perc / 100.0 / sl_dist))
    if direction == "SHORT":
        units = -units

    body = {
        "order": {
            "type": "MARKET",
            "instrument": _INSTRUMENT,
            "units": str(units),
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {"price": f"{sl:.3f}"},
            "takeProfitOnFill": {"price": f"{tp:.3f}"},
        }
    }
    try:
        r = requests.post(_account_url("/orders"), headers=_headers(), json=body, timeout=_TIMEOUT)
        if r.status_code >= 300:
            return f"errore-ordine: {r.status_code} {r.text[:200]}"
        fill = r.json().get("orderFillTransaction")
        if fill:
            return f"ESEGUITO {direction} {units} @ {fill.get('price')} (SL {sl:.2f}/TP {tp:.2f})"
        return f"ordine-inviato (nessun fill immediato): {r.json().get('orderCreateTransaction', {}).get('id')}"
    except Exception as exc:  # noqa: BLE001
        return f"errore-eccezione: {exc}"
