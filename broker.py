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
import time

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


def test_trade() -> str:
    """Test end-to-end: apre una posizione GOLD minima sul demo e la richiude
    subito. Ritorna 'OK: ...' se il giro completo funziona, altrimenti 'ERR: ...'."""
    tok = _login()
    if not tok:
        return "ERR: sessione non creata (credenziali?)"
    cst, xst = tok
    h = _h(cst, xst)
    acc = os.getenv("CAPITAL_ACCOUNT_ID", "")
    if acc:
        try:
            requests.put(f"{_BASE}/api/v1/session", headers=h, json={"accountId": acc}, timeout=_TIMEOUT)
        except Exception:
            pass

    minsize, bid = 1.0, None
    try:
        mk = requests.get(f"{_BASE}/api/v1/markets/{_EPIC}", headers=h, timeout=_TIMEOUT).json()
        minsize = float(mk.get("dealingRules", {}).get("minDealSize", {}).get("value", 1) or 1)
        bid = float(mk.get("snapshot", {}).get("bid", 0) or 0) or None
    except Exception:
        pass

    # Apertura posizione minima (senza SL/TP: la chiudiamo subito).
    body = {"epic": _EPIC, "direction": "BUY", "size": minsize}
    r = requests.post(f"{_BASE}/api/v1/positions", headers=h, json=body, timeout=_TIMEOUT)
    if r.status_code >= 300:
        return f"ERR: apertura fallita {r.status_code} {r.text[:180]}"
    ref = r.json().get("dealReference", "")

    time.sleep(2)  # attende la conferma
    try:
        conf = requests.get(f"{_BASE}/api/v1/confirms/{ref}", headers=h, timeout=_TIMEOUT).json()
        if conf.get("dealStatus") != "ACCEPTED":
            return f"ERR: ordine non accettato ({conf.get('reason')})"
    except Exception:
        pass

    # Chiude tutte le posizioni GOLD (dovrebbe esserci solo la nostra di test).
    chiuse = 0
    try:
        pos = requests.get(f"{_BASE}/api/v1/positions", headers=h, timeout=_TIMEOUT).json()
        for p in pos.get("positions", []):
            if p.get("market", {}).get("epic") == _EPIC:
                deal_id = p.get("position", {}).get("dealId")
                if deal_id:
                    requests.delete(f"{_BASE}/api/v1/positions/{deal_id}", headers=h, timeout=_TIMEOUT)
                    chiuse += 1
    except Exception as exc:  # noqa: BLE001
        return f"OK-parziale: aperto (~{bid}) ma chiusura non confermata ({exc}). Controlla l'app."

    if chiuse:
        return f"OK: aperto e richiuso {chiuse} posizione/i GOLD (prezzo ~{bid}, size {minsize}). Esecuzione FUNZIONA."
    return f"OK-parziale: ordine accettato (ref {ref}) ma nessuna posizione da chiudere trovata. Controlla l'app."


def _select_account(h: dict) -> None:
    acc = os.getenv("CAPITAL_ACCOUNT_ID", "")
    if acc:
        try:
            requests.put(f"{_BASE}/api/v1/session", headers=h, json={"accountId": acc}, timeout=_TIMEOUT)
        except Exception:
            pass


def open_test_position() -> str:
    """Apre una posizione GOLD di prova e la LASCIA aperta (SL/TP larghi),
    cosi' e' visibile nell'app. Da chiudere poi con close_all_gold()."""
    tok = _login()
    if not tok:
        return "ERR: sessione non creata"
    cst, xst = tok
    h = _h(cst, xst)
    _select_account(h)
    try:
        mk = requests.get(f"{_BASE}/api/v1/markets/{_EPIC}", headers=h, timeout=_TIMEOUT).json()
        minsize = float(mk.get("dealingRules", {}).get("minDealSize", {}).get("value", 1) or 1)
        bid = float(mk.get("snapshot", {}).get("bid", 0) or 0) or 2000.0
    except Exception:
        minsize, bid = 1.0, 2000.0
    body = {"epic": _EPIC, "direction": "BUY", "size": minsize,
            "stopLevel": round(bid * 0.85, 2), "profitLevel": round(bid * 1.15, 2)}
    r = requests.post(f"{_BASE}/api/v1/positions", headers=h, json=body, timeout=_TIMEOUT)
    if r.status_code >= 300:
        return f"ERR: apertura fallita {r.status_code} {r.text[:180]}"
    # su quale conto?
    acc_id = ""
    try:
        acc_id = requests.get(f"{_BASE}/api/v1/session", headers=h, timeout=_TIMEOUT).json().get("accountId", "")
    except Exception:
        pass
    return f"OK: aperta posizione GOLD di prova (~{bid}, size {minsize}) sul conto {acc_id}. Guardala nell'app, poi la chiudo."


def close_all_gold() -> str:
    """Chiude tutte le posizioni GOLD aperte (per ripulire dopo il test)."""
    tok = _login()
    if not tok:
        return "ERR: sessione non creata"
    cst, xst = tok
    h = _h(cst, xst)
    _select_account(h)
    chiuse = 0
    try:
        pos = requests.get(f"{_BASE}/api/v1/positions", headers=h, timeout=_TIMEOUT).json()
        for p in pos.get("positions", []):
            if p.get("market", {}).get("epic") == _EPIC:
                deal_id = p.get("position", {}).get("dealId")
                if deal_id:
                    requests.delete(f"{_BASE}/api/v1/positions/{deal_id}", headers=h, timeout=_TIMEOUT)
                    chiuse += 1
    except Exception as exc:  # noqa: BLE001
        return f"ERR: {exc}"
    return f"OK: chiuse {chiuse} posizione/i GOLD."


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
