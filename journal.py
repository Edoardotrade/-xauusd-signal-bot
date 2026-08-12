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

# Profilo (vuoto = bot 1). Ogni profilo ha il suo registro separato.
_PROFILE = os.getenv("PROFILE", "").strip()
_SUFFIX = f"_{_PROFILE}" if _PROFILE else ""
LOG_PATH = os.path.join(os.path.dirname(__file__), f"signals_log{_SUFFIX}.csv")
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


def open_count() -> int:
    """Numero di trade attualmente APERTI (per questo profilo)."""
    return sum(1 for r in _read() if r["status"] == "OPEN")


def losses_today(now: datetime | None = None) -> int:
    """Numero di trade CHIUSI IN PERDITA oggi (data ITALIANA), per questo profilo.

    Serve al freno 'stop dopo N perdite al giorno': conta solo gli esiti LOSS
    (le scadenze a 0R non contano come perdita). Usa la data di chiusura.
    """
    now = now or datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        rome = ZoneInfo("Europe/Rome")
    except Exception:
        rome = None
    oggi = (now.astimezone(rome) if rome else now).strftime("%Y-%m-%d")
    n = 0
    for r in _read():
        if r["status"] != "LOSS":
            continue
        closed = (r.get("closed_utc") or "").strip()
        if not closed:
            continue
        try:
            ts = datetime.strptime(closed, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        giorno = (ts.astimezone(rome) if rome else ts).strftime("%Y-%m-%d")
        if giorno == oggi:
            n += 1
    return n


def recent_closed_text(n: int = 10) -> str:
    """Testo HTML con le ultime N operazioni CHIUSE (esito + R)."""
    chiusi = [r for r in _read() if r["status"] in ("WIN", "LOSS", "EXPIRED")]
    if not chiusi:
        return "🗒 <b>Storico operazioni</b>\nNessuna operazione chiusa ancora."
    ultime = chiusi[-n:]
    righe = [f"🗒 <b>Ultime {len(ultime)} operazioni chiuse</b>"]
    for r in reversed(ultime):  # più recenti in alto
        em = "✅" if r["status"] == "WIN" else ("❌" if r["status"] == "LOSS" else "➖")
        quando = (r.get("closed_utc") or r.get("bar_time") or "")[:10]
        righe.append(f"{em} {quando} · {r['timeframe']} {r['direction']} → {r['result_R']}R")
    return "\n".join(righe)


def _stats(chiusi: list[dict]) -> dict:
    """Metriche professionali su una lista di trade chiusi (WIN/LOSS)."""
    rs = [float(r["result_R"]) for r in chiusi]
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x <= 0]
    tot = len(rs)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    # Max drawdown sulla curva equity (in R) e streak di perdite.
    eq = 0.0
    peak = 0.0
    max_dd = 0.0
    streak = worst_streak = 0
    for x in rs:
        eq += x
        peak = max(peak, eq)
        max_dd = min(max_dd, eq - peak)
        if x <= 0:
            streak += 1
            worst_streak = max(worst_streak, streak)
        else:
            streak = 0
    return {
        "n": tot,
        "wins": len(wins),
        "win_rate": 100 * len(wins) / tot if tot else 0.0,
        "net_R": sum(rs),
        "expectancy": sum(rs) / tot if tot else 0.0,
        "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf"),
        "avg_win": (gross_win / len(wins)) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
        "max_dd": max_dd,
        "worst_streak": worst_streak,
    }


def summary_text(risk_perc: float = 1.0) -> str:
    """Report professionale del paper-trading (totale + per timeframe)."""
    rows = _read()
    chiusi = [r for r in rows if r["status"] in ("WIN", "LOSS")]
    aperti = [r for r in rows if r["status"] == "OPEN"]
    if not chiusi:
        return (f"📊 <b>Report paper-trading</b>\nNessun trade chiuso ancora. "
                f"Segnali aperti: {len(aperti)}.")

    s = _stats(chiusi)
    pf = "∞" if s["profit_factor"] == float("inf") else f"{s['profit_factor']:.2f}"
    rendimento = s["net_R"] * risk_perc  # ogni R = risk_perc% del conto

    out = [f"📊 <b>Report paper-trading</b>", ""]

    # Dettaglio per timeframe.
    tfs = []
    for tf in ["Daily", "4H", "1H", "15M"]:
        tf_rows = [r for r in chiusi if r["timeframe"] == tf]
        if tf_rows:
            st = _stats(tf_rows)
            mark = "🟢" if tf == "Daily" else "🧪"
            tfs.append(f"{mark} <b>{tf}</b>: {st['n']} trade · win {st['win_rate']:.0f}% · {st['net_R']:+.1f}R")
    if tfs:
        out += ["<b>Per timeframe:</b>"] + tfs + [""]

    out += [
        "<b>TOTALE</b>",
        f"• Trade chiusi: <b>{s['n']}</b> (vinti {s['wins']}, persi {s['n'] - s['wins']})",
        f"• Win rate: <b>{s['win_rate']:.1f}%</b>",
        f"• Risultato: <b>{s['net_R']:+.2f}R</b>  (~{rendimento:+.1f}% sul conto demo)",
        f"• Expectancy: <b>{s['expectancy']:+.3f}R</b>/trade",
        f"• Profit factor: <b>{pf}</b>  (&gt;1 = in profitto)",
        f"• Media vinta {s['avg_win']:+.2f}R · media persa {s['avg_loss']:+.2f}R",
        f"• Max drawdown: <b>{s['max_dd']:.2f}R</b> · peggior serie perdite: {s['worst_streak']}",
        f"• Segnali aperti: {len(aperti)}",
        "",
        "<i>Risultati sul future GC=F. Confronta col backtest (Daily ~52% win, "
        "+0.29R). Gli intraday nel backtest PERDONO. Non è consulenza finanziaria.</i>",
    ]
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(summary_text())
