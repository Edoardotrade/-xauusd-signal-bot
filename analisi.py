"""Analisi di mercato XAUUSD su richiesta (comando /analisi del listener).

Restituisce un testo HTML con: trend di fondo, forza (ADX), momentum (RSI),
volatilita' (ATR), livelli chiave e cosa 'vedono' le strategie in questo
momento. E' INFORMATIVO, non e' consulenza finanziaria.
"""
from __future__ import annotations

from datetime import datetime, timezone

from config import Config
from data import fetch_ohlc, fetch_spot_price
from strategy import ema, rsi, atr, adx, generate


def _trend_label(price: float, e20: float, e50: float, e200: float) -> str:
    if price > e200 and e20 > e50 and price > e20:
        return "🟢 <b>Rialzista forte</b>"
    if price > e200:
        return "🟢 <b>Rialzista</b>"
    if price < e200 and e20 < e50 and price < e20:
        return "🔴 <b>Ribassista forte</b>"
    if price < e200:
        return "🔴 <b>Ribassista</b>"
    return "🟡 <b>Neutro / laterale</b>"


def _adx_label(a: float) -> str:
    if a >= 40:
        return f"molto forte ({a:.0f})"
    if a >= 25:
        return f"forte ({a:.0f})"
    if a >= 20:
        return f"moderata ({a:.0f})"
    return f"debole ({a:.0f}) → mercato laterale"


def _rsi_label(r: float) -> str:
    if r >= 70:
        return f"{r:.0f} (ipercomprato)"
    if r <= 30:
        return f"{r:.0f} (ipervenduto)"
    return f"{r:.0f} (neutro)"


def _sig_label(direction: str) -> str:
    return {"LONG": "🟢 LONG", "SHORT": "🔴 SHORT"}.get(direction, "⚪️ fermo (NO-TRADE)")


def build_analisi() -> str:
    """Costruisce il messaggio HTML di analisi del mercato oro."""
    cfg = Config.load()
    spot = fetch_spot_price()
    dd = fetch_ohlc(cfg.symbol, interval="1d", period="2y")

    price = float(dd["close"].iloc[-1])
    disp = spot if spot else price
    e20 = float(ema(dd["close"], 20).iloc[-1])
    e50 = float(ema(dd["close"], 50).iloc[-1])
    e200 = float(ema(dd["close"], 200).iloc[-1])
    a = float(adx(dd, 14).iloc[-1])
    r = float(rsi(dd["close"], 14).iloc[-1])
    at = float(atr(dd, 14).iloc[-1])

    # Cosa 'vedono' le strategie trend ora (Daily e 1H).
    sig_d = generate(dd, cfg, spot_price=spot)
    hh = fetch_ohlc(cfg.symbol, interval="1h")
    sig_h = generate(hh, cfg, spot_price=spot)

    # Canale di breakout 1H (bot 3): dentro o vicino a una rottura?
    hi20 = float(hh["high"].rolling(20).max().shift(1).iloc[-1])
    lo20 = float(hh["low"].rolling(20).min().shift(1).iloc[-1])
    hc = float(hh["close"].iloc[-1])
    if hc > hi20:
        brk = "🟢 rottura rialzista in corso"
    elif hc < lo20:
        brk = "🔴 rottura ribassista in corso"
    else:
        vicino = "vicino" if (hi20 - hc) < at or (hc - lo20) < at else "lontano"
        brk = f"dentro il canale ({vicino} ai bordi {lo20:.0f}–{hi20:.0f})"

    # Distanza dalla EMA200 (la linea del trend di fondo).
    dist200 = (price - e200) / e200 * 100

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    out = [
        f"📊 <b>Analisi mercato XAUUSD</b> — {now}",
        "",
        f"<b>Prezzo spot:</b> {disp:.2f}",
        f"<b>Trend di fondo:</b> {_trend_label(price, e20, e50, e200)}",
        f"<b>Forza trend (ADX):</b> {_adx_label(a)}",
        f"<b>Momentum (RSI):</b> {_rsi_label(r)}",
        f"<b>Volatilità (ATR):</b> {at:.1f} $",
        f"<b>EMA200 (linea di tendenza):</b> {e200:.0f}  (prezzo {dist200:+.1f}%)",
        "",
        "<b>Cosa vedono le strategie ora:</b>",
        f"• Trend Daily: {_sig_label(sig_d.direction)}",
        f"• Trend 1H: {_sig_label(sig_h.direction)}",
        f"• Breakout 1H: {brk}",
        "",
        f"<i>{_sintesi(sig_d, a, r, dist200)}</i>",
        "",
        "⚠️ <b>Analisi informativa, non è consulenza finanziaria.</b> "
        "Le uscite dei bot sono automatiche (stop/target/trailing): "
        "intervenire a mano di solito peggiora un sistema automatico.",
    ]
    return "\n".join(out)


def _sintesi(sig_d, adx_val: float, rsi_val: float, dist200: float) -> str:
    """Lettura in parole semplici della situazione."""
    if adx_val < 20:
        return ("Mercato senza direzione chiara (ADX debole): fase laterale, "
                "i trend-follower stanno prudenti. Meglio aspettare un trend definito.")
    if sig_d.direction == "LONG":
        return ("Trend rialzista con forza sufficiente: il sistema è dalla parte "
                "dei compratori. Finché regge, si lascia correre.")
    if sig_d.direction == "SHORT":
        return ("Trend ribassista con forza sufficiente: il sistema è dalla parte "
                "dei venditori. Finché regge, si lascia correre.")
    if dist200 > 0:
        return ("Trend di fondo ancora rialzista ma senza un ingresso pulito adesso: "
                "il sistema aspetta un allineamento migliore prima di operare.")
    return ("Nessun ingresso chiaro ora: il sistema resta fermo e aspetta "
            "condizioni migliori.")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(build_analisi())
