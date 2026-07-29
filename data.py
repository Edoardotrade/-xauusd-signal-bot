"""Scarica i dati di prezzo dell'oro dall'API pubblica di Yahoo Finance.

Chiamata diretta all'endpoint chart (con User-Agent da browser): più robusta
rispetto a librerie che vengono spesso bloccate da Yahoo.
"""
from __future__ import annotations

import pandas as pd
import requests

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def fetch_daily(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Scarica candele giornaliere e restituisce un DataFrame pulito.

    Colonne garantite: open, high, low, close, volume (minuscole).
    L'ultima riga è la candela giornaliera più recente.
    """
    resp = requests.get(
        _CHART_URL.format(symbol=symbol),
        params={"range": period, "interval": "1d"},
        headers=_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    result = (data.get("chart") or {}).get("result")
    if not result:
        err = (data.get("chart") or {}).get("error")
        raise RuntimeError(f"Nessun dato per '{symbol}'. Risposta Yahoo: {err}")

    node = result[0]
    timestamps = node.get("timestamp")
    quote = (node.get("indicators", {}).get("quote") or [{}])[0]
    if not timestamps or not quote:
        raise RuntimeError(f"Dati incompleti per '{symbol}'. Simbolo errato?")

    df = pd.DataFrame(
        {
            "open": quote.get("open"),
            "high": quote.get("high"),
            "low": quote.get("low"),
            "close": quote.get("close"),
            "volume": quote.get("volume"),
        },
        index=pd.to_datetime(timestamps, unit="s"),
    )
    df = df.dropna(subset=["open", "high", "low", "close"])
    if df.empty:
        raise RuntimeError(f"Nessuna candela valida per '{symbol}'.")
    return df


def fetch_spot_price() -> float | None:
    """Prezzo spot XAUUSD corrente da gold-api.com (gratis, senza chiave).

    Serve a mostrare prezzo/SL/TP in linea con lo spot delle piattaforme forex
    (il future GC=F usato per lo storico ha un premio di ~50-70 punti).
    Ritorna None se la fonte non risponde, così il bot ripiega sul future.
    """
    try:
        resp = requests.get(
            "https://api.gold-api.com/price/XAU",
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        price = float(resp.json().get("price"))
        return price if price > 0 else None
    except Exception:
        return None
