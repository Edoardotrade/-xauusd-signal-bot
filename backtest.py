"""Backtest onesto della strategia su dati storici XAUUSD.

Simula: quando la strategia genera un segnale, apre un trade con lo stop-loss
e il take-profit definiti dalla strategia, poi controlla nelle candele
SUCCESSIVE se viene toccato prima lo SL o il TP. Nessun look-ahead bias.

Uso:
    python backtest.py                 # ultimi 5 anni
    python backtest.py --period 10y    # periodo Yahoo Finance (es. 2y, 5y, 10y, max)

⚠️ Un backtest positivo NON garantisce profitti futuri. Serve a scartare le
strategie chiaramente perdenti, non a promettere guadagni.
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

# Su Windows la console usa cp1252 e va in crash sugli emoji/simboli: forziamo UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import Config
from data import fetch_ohlc
from strategy import adx, atr, ema, rsi


def backtest(df: pd.DataFrame, cfg: Config) -> dict:
    df = df.copy()
    df["ema_fast"] = ema(df["close"], cfg.ema_fast)
    df["ema_slow"] = ema(df["close"], cfg.ema_slow)
    df["rsi"] = rsi(df["close"], cfg.rsi_period)
    df["atr"] = atr(df, cfg.atr_period)
    df["adx"] = adx(df, cfg.adx_period)
    df = df.dropna()

    trades: list[float] = []  # R multipli (+RR per win, -1 per loss)
    durations: list[int] = []  # barre trascorse fino all'esito (SL o TP)
    i = 0
    n = len(df)
    while i < n - 1:
        row = df.iloc[i]
        price = float(row["close"])
        ef, es = float(row["ema_fast"]), float(row["ema_slow"])
        r, a, atr_val = float(row["rsi"]), float(row["adx"]), float(row["atr"])

        uptrend = ef > es and price > ef
        downtrend = ef < es and price < ef
        trend_strong = a >= cfg.adx_min

        direction = None
        if trend_strong and uptrend and 50 <= r <= 70:
            direction = "LONG"
        elif trend_strong and downtrend and 30 <= r <= 50:
            direction = "SHORT"

        if direction is None:
            i += 1
            continue

        if direction == "LONG":
            sl = price - cfg.atr_sl_mult * atr_val
            tp = price + cfg.atr_sl_mult * atr_val * cfg.risk_reward
        else:
            sl = price + cfg.atr_sl_mult * atr_val
            tp = price - cfg.atr_sl_mult * atr_val * cfg.risk_reward

        # Cerca l'esito nelle candele successive (max 30 giorni in trade).
        outcome = None
        for j in range(i + 1, min(i + 31, n)):
            hi = float(df.iloc[j]["high"])
            lo = float(df.iloc[j]["low"])
            if direction == "LONG":
                if lo <= sl:
                    outcome = -1.0
                    break
                if hi >= tp:
                    outcome = cfg.risk_reward
                    break
            else:
                if hi >= sl:
                    outcome = -1.0
                    break
                if lo <= tp:
                    outcome = cfg.risk_reward
                    break
        if outcome is None:
            # Trade non chiuso entro la finestra: lo ignoriamo (conservativo).
            i += 1
            continue

        trades.append(outcome)
        durations.append(j - i)  # barre trascorse dall'ingresso all'esito
        i = j + 1  # evita trade sovrapposti

    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t <= 0]
    total = len(trades)
    net_r = sum(trades)
    sorted_dur = sorted(durations)
    median_dur = sorted_dur[len(sorted_dur) // 2] if sorted_dur else 0
    return {
        "avg_bars": (sum(durations) / len(durations)) if durations else 0.0,
        "median_bars": median_dur,
        "max_bars": max(durations) if durations else 0,
        "trades": total,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": (len(wins) / total * 100) if total else 0.0,
        "net_R": net_r,
        "avg_R_per_trade": (net_r / total) if total else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Backtest strategia XAUUSD")
    parser.add_argument("--interval", default="1d", help="Timeframe: 1d (default) o 1h")
    parser.add_argument("--period", default=None, help="Periodo Yahoo Finance (default per timeframe)")
    args = parser.parse_args()

    cfg = Config.load()
    df = fetch_ohlc(cfg.symbol, interval=args.interval, period=args.period)
    res = backtest(df, cfg)

    print("=" * 48)
    print(f"BACKTEST XAUUSD ({cfg.symbol}) — {args.interval}, {len(df)} barre")
    print("=" * 48)
    print(f"Trade totali : {res['trades']}")
    print(f"Vinti        : {res['wins']}")
    print(f"Persi        : {res['losses']}")
    print(f"Win rate     : {res['win_rate']:.1f}%")
    print(f"R netto       : {res['net_R']:+.2f}R")
    print(f"R medio/trade : {res['avg_R_per_trade']:+.3f}R")
    unit = "giorni" if args.interval == "1d" else "barre"
    print(f"Durata trade : media {res['avg_bars']:.1f} {unit}, "
          f"mediana {res['median_bars']} {unit}, max {res['max_bars']} {unit}")
    print("-" * 48)
    if res["avg_R_per_trade"] > 0.05:
        print("Esito: possibile edge POSITIVO. Prosegui con paper-trading.")
    else:
        print("Esito: NESSUN edge chiaro. NON usare soldi veri con questi parametri.")
    print("⚠️ Il passato non garantisce il futuro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
