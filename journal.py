"""Registro dei segnali per il paper-trading automatico.

Salva ogni segnale reale (LONG/SHORT) in signals_log.csv e, ad ogni
esecuzione, verifica se i segnali ancora aperti hanno toccato SL o TP,
usando lo storico del future GC=F (le distanze SL/TP sono identiche a spot).

Cosi' puoi confrontare il risultato REALE con il backtest.
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone

import pandas as pd

LOG_PATH = os.path.join(os.path.dirname(__file__), "signals_log.csv")
FIELDS = [
    "logged_utc", "timeframe", "bar_time", "direction",
    "entry_ref", "sl_ref", "tp_ref", "rr",
    "status", "result_R", "closed_utc",
]
MAX_BARS = 30  # dopo 30 barre senza esito il trade e' considerato scaduto


def _read() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _write(rows: list[dict]) -> None:
    with open(LOG_PATH, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def record(timeframe: str, bar_time: str, direction: str,
           entry_ref: float, sl_ref: float, tp_ref: float, rr: float) -> bool:
    """Registra un nuovo segnale (se non gia' presente per quella barra)."""
    rows = _read()
    for r in rows:
        if r["timeframe"] == timeframe and r["bar_time"] == bar_time:
            return False  # gia' registrato: evita doppioni
        if r["timeframe"] == timeframe and r["status"] == "OPEN":
            return False  # un trade alla volta: non sovrapporre (come nel backtest)
    rows.append({
        "logged_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        "timeframe": timeframe, "bar_time": bar_time, "direction": direction,
        "entry_ref": f"{entry_ref:.2f}", "sl_ref": f"{sl_ref:.2f}",
        "tp_ref": f"{tp_ref:.2f}", "rr": f"{rr:.2f}",
        "status": "OPEN", "result_R": "", "closed_utc": "",
    })
    _write(rows)
    return True


def update_open(timeframe: str, df: pd.DataFrame) -> int:
    """Verifica i trade aperti di questo timeframe contro le candele successive.
    Ritorna il numero di trade chiusi in questa esecuzione."""
    rows = _read()
    if not rows:
        return 0
    closed = 0
    for r in rows:
        if r["status"] != "OPEN" or r["timeframe"] != timeframe:
            continue
        bar_time = pd.to_datetime(r["bar_time"])
        after = df[df.index > bar_time]
        if len(after) == 0:
            continue  # ancora nessuna candela nuova
        direction = r["direction"]
        sl, tp, rr = float(r["sl_ref"]), float(r["tp_ref"]), float(r["rr"])
        esito = None
        closed_ts = None
        for ts, row in after.head(MAX_BARS).iterrows():
            hi, lo = float(row["high"]), float(row["low"])
            if direction == "LONG":
                if lo <= sl:
                    esito = -1.0; closed_ts = ts; break
                if hi >= tp:
                    esito = rr; closed_ts = ts; break
            else:  # SHORT
                if hi >= sl:
                    esito = -1.0; closed_ts = ts; break
                if lo <= tp:
                    esito = rr; closed_ts = ts; break
        if esito is not None:
            r["status"] = "WIN" if esito > 0 else "LOSS"
            r["result_R"] = f"{esito:+.2f}"
            r["closed_utc"] = closed_ts.strftime("%Y-%m-%d %H:%M:%S")
            closed += 1
        elif len(after) >= MAX_BARS:
            r["status"] = "EXPIRED"
            r["result_R"] = "0"
            r["closed_utc"] = after.index[MAX_BARS - 1].strftime("%Y-%m-%d %H:%M:%S")
            closed += 1
    if closed:
        _write(rows)
    return closed


def summary_text(timeframe: str | None = None) -> str:
    """Riepilogo leggibile dei risultati chiusi (opz. filtrato per timeframe)."""
    rows = _read()
    if timeframe:
        rows = [r for r in rows if r["timeframe"] == timeframe]
    chiusi = [r for r in rows if r["status"] in ("WIN", "LOSS")]
    aperti = [r for r in rows if r["status"] == "OPEN"]
    if not chiusi:
        return (f"📊 <b>Report paper-trading</b>\nNessun trade chiuso ancora. "
                f"Segnali aperti: {len(aperti)}.")
    wins = [r for r in chiusi if r["status"] == "WIN"]
    net_r = sum(float(r["result_R"]) for r in chiusi)
    tot = len(chiusi)
    wr = 100 * len(wins) / tot
    scope = f" ({timeframe})" if timeframe else ""
    return (
        f"📊 <b>Report paper-trading{scope}</b>\n"
        f"Trade chiusi: <b>{tot}</b>\n"
        f"Vinti: {len(wins)} · Persi: {tot - len(wins)}\n"
        f"Win rate: <b>{wr:.1f}%</b>\n"
        f"Risultato totale: <b>{net_r:+.2f}R</b>\n"
        f"Segnali ancora aperti: {len(aperti)}\n\n"
        f"<i>Risultati calcolati sul future GC=F. Confronta col backtest "
        f"(Daily ~52% win, +0.29R). Non è consulenza finanziaria.</i>"
    )


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(summary_text())
