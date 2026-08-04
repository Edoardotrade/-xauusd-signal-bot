"""Esecutore automatico su conto DEMO Capital.com.

SICUREZZA: parla SOLO con l'endpoint DEMO (demo-api-capital.backend-capital.com).
Non esegue e non deve MAI eseguire su conti reali. Nessun trade con soldi veri.

Credenziali (dai secrets del workflow):
  CAPITAL_API_KEY      chiave API (generata nell'app Capital.com)
  CAPITAL_IDENTIFIER   email di login
  CAPITAL_PASSWORD     password della chiave API
  CAPITAL_ACCOUNT_ID   (opzionale) id del conto demo su cui operare

Modello: UNA posizione alla volta per conto (come nel trading reale). Se c'è
già una posizione aperta sull'oro, il nuovo segnale viene saltato.
"""
from __future__ import annotations

import os

import requests

# --- SOLO DEMO: endpoint practice fisso. Non modificare verso il conto reale. ---
_BASE = "https://demo-api-capital.backend-capital.com"
_EPIC = "GOLD"          # oro spot su Capital.com
_TIMEOUT = 20


def enabled() -> bool:
    return bool(os.getenv("CAPITAL_API_KEY") and os.getenv("CAPITAL_IDENTIFIER")
                and os.getenv("CAPITAL_PASSWORD"))


def _login() -> tuple[str, str] | None:
    """Crea una sessione e ritorna (CST, X-SECURITY-TOKEN). None se fallisce."""
    try:
        r = requests.post(
            f"{_BASE}/api/v1/session",
            headers={"X-CAP-API-KEY": os.getenv("CAPITAL_API_KEY", ""),
                     "Content-Type": "application/json"},
            json={"identifier": os.getenv("CAPITAL_IDENTIFIER", ""),
                  "password": os.getenv("CAPITAL_PASSWORD", "")},
            timeout=_TIMEOUT,
        )
        if r.status_code >= 300:
            print(f"[broker] login fallito: {r.status_code} {r.text[:150]}")
            return None
        return r.headers.get("CST", ""), r.headers.get("X-SECURITY-TOKEN", "")
    except Exception as exc:  # noqa: BLE001
        print(f"[broker] errore login: {exc}")
        return None


def _h(cst: str, xst: str) -> dict:
    return {"X-CAP-API-KEY": os.getenv("CAPITAL_API_KEY", ""),
            "CST": cst, "X-SECURITY-TOKEN": xst, "Content-Type": "application/json"}


def status() -> dict | None:
    """Verifica la connessione: login + lettura conti. None se fallisce.
    Non apre nessun trade. Serve per il test delle credenziali."""
    tok = _login()
    if not tok:
        return None
    cst, xst = tok
    try:
        accs = requests.get(f"{_BASE}/api/v1/accounts", headers=_h(cst, xst),
                            timeout=_TIMEOUT).json()
        conti = [{"id": a.get("accountId"), "saldo": a.get("balance", {}).get("balance")}
                 for a in accs.get("accounts", [])]
        return {"ok": True, "conti": conti}
    except Exception as exc:  # noqa: BLE001
        print(f"[broker] errore lettura conti: {exc}")
        return None


def execute_if_flat(direction: str, entry: float, sl: float, tp: float,
                    risk_perc: float) -> str:
    tok = _login()
    if not tok:
        return "no-sessione"
    cst, xst = tok
    h = _h(cst, xst)

    # Seleziona il conto demo indicato (se fornito).
    acc_id = os.getenv("CAPITAL_ACCOUNT_ID", "")
    if acc_id:
        try:
            requests.put(f"{_BASE}/api/v1/session", headers=h,
                         json={"accountId": acc_id}, timeout=_TIMEOUT)
        except Exception:
            pass

    # Una posizione alla volta: se ce n'è già una aperta, salta.
    try:
        pos = requests.get(f"{_BASE}/api/v1/positions", headers=h, timeout=_TIMEOUT).json()
        if pos.get("positions"):
            return "posizione-gia-aperta"
    except Exception as exc:  # noqa: BLE001
        return f"errore-lettura-posizioni: {exc}"

    # Saldo del conto demo per la size al rischio.
    try:
        accs = requests.get(f"{_BASE}/api/v1/accounts", headers=h, timeout=_TIMEOUT).json()
        bal = 0.0
        for a in accs.get("accounts", []):
            if not acc_id or a.get("accountId") == acc_id:
                bal = float(a.get("balance", {}).get("balance", 0) or 0)
                break
    except Exception as exc:  # noqa: BLE001
        return f"errore-saldo: {exc}"

    sl_dist = abs(entry - sl)
    if bal <= 0 or sl_dist <= 0:
        return "dati-non-validi"

    # Size al rischio (approssimata: 1 unità ~ 1 oz). Su demo eventuali scostamenti
    # sono innocui; si affina dopo il primo fill reale.
    size = round(bal * risk_perc / 100.0 / sl_dist, 2)
    if size <= 0:
        size = 0.01

    body = {
        "epic": _EPIC,
        "direction": "BUY" if direction == "LONG" else "SELL",
        "size": size,
        "stopLevel": round(sl, 2),
        "profitLevel": round(tp, 2),
        "guaranteedStop": False,
    }
    try:
        r = requests.post(f"{_BASE}/api/v1/positions", headers=h, json=body, timeout=_TIMEOUT)
        if r.status_code >= 300:
            return f"errore-ordine: {r.status_code} {r.text[:200]}"
        ref = r.json().get("dealReference", "?")
        return f"ESEGUITO {direction} size {size} (SL {sl:.2f}/TP {tp:.2f}) ref {ref}"
    except Exception as exc:  # noqa: BLE001
        return f"errore-eccezione: {exc}"
