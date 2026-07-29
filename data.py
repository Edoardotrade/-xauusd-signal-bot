"""Scarica i dati di prezzo dell'oro dall'API pubblica di Yahoo Finance.

Chiamata diretta all'endpoint chart (con User-Agent da browser): più robusta
rispetto a librerie che vengono spesso bloccate da Yahoo.
"""
from __future__ import annotations

import pandas as pd
import requests

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# Range di storico consigliato per ogni timeframe (abbastanza barre per gli indicatori).
_DEFAULT_RANGE = {"1d": "1y", "1h": "3mo", "60m": "3mo", "30m": "1mo", "15m": "1mo"}


def fetch_ohlc(symbol: str, interval: str = "1d", period: str | None = None) -> pd.DataFrame:
    """Scarica candele OHLC per il timeframe richiesto e restituisce un DataFrame pulito.

    interval: "1d" (giornaliero) oppure "1h" (orario), ecc.
    period:   range storico; se None usa un default sensato per il timeframe.
    Colonne garantite: open, high, low, close, volume (minuscole).
    """
    if period is None:
        period = _DEFAULT_RANGE.get(interval, "1y")
    resp = requests.get(
        _CHART_URL.format(symbol=symbol),
        params={"range": period, "interval": interval},
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


def fetch_daily(symbol: str, period: str = "1y") -> pd.DataFrame:
    """Compatibilità: candele giornaliere (equivale a fetch_ohlc interval='1d')."""
    return fetch_ohlc(symbol, interval="1d", period=period)


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
