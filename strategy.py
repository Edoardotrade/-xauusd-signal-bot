"""Indicatori tecnici e generazione del segnale giornaliero per XAUUSD.

Strategia: trend-following con conferma di momentum e filtro di forza del trend.
  - Direzione trend: EMA veloce vs EMA lenta
  - Momentum:        RSI (evita ingressi in ipercomprato/ipervenduto estremi)
  - Forza trend:     ADX (opera solo se il trend è abbastanza forte)
  - Rischio:         ATR per dimensionare stop-loss e take-profit sulla
                     volatilità REALE, non su valori arbitrari.

NB: è una strategia ragionevole e documentata, NON una garanzia di profitto.
Va sempre validata con backtest + paper-trading prima di usare soldi veri.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from config import Config


# --------------------------------------------------------------------------- #
# Indicatori (implementati con pandas per evitare dipendenze come TA-Lib)
# --------------------------------------------------------------------------- #
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50.0)


def _true_range(df: pd.DataFrame) -> pd.Series:
    high, low, prev_close = df["high"], df["low"], df["close"].shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    return tr


def atr(df: pd.DataFrame, period: int) -> pd.Series:
    return _true_range(df).ewm(alpha=1 / period, adjust=False).mean()


def adx(df: pd.DataFrame, period: int) -> pd.Series:
    """Average Directional Index: misura la forza del trend (0-100)."""
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = _true_range(df)
    atr_ = tr.ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * pd.Series(plus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False
    ).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).ewm(
        alpha=1 / period, adjust=False
    ).mean() / atr_

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1 / period, adjust=False).mean().fillna(0.0)


# --------------------------------------------------------------------------- #
# Segnale
# --------------------------------------------------------------------------- #
@dataclass
class Signal:
    direction: str  # "LONG", "SHORT" oppure "NO-TRADE"
    price: float
    stop_loss: float | None
    take_profit: float | None
    rr: float | None
    ema_fast: float
    ema_slow: float
    rsi: float
    adx: float
    atr: float
    reason: str
    price_is_spot: bool = False  # True se il prezzo mostrato e' lo spot XAUUSD
    decision_price: float = 0.0  # chiusura future usata per la decisione (per il log)
    confidence: int = 0          # affidabilita' del segnale 0-100 (0 se NO-TRADE)


def generate(df: pd.DataFrame, cfg: Config, spot_price: float | None = None) -> Signal:
    """Genera il segnale.

    La DIREZIONE si decide sullo storico del future GC=F (df).
    Se `spot_price` e' fornito (spot XAUUSD corrente), prezzo/SL/TP vengono
    mostrati in termini di spot, cosi' coincidono con le piattaforme forex.
    L'ATR e' una DISTANZA di prezzo, quindi vale allo stesso modo su spot e future.
    """
    df = df.copy()
    df["ema_fast"] = ema(df["close"], cfg.ema_fast)
    df["ema_slow"] = ema(df["close"], cfg.ema_slow)
    df["rsi"] = rsi(df["close"], cfg.rsi_period)
    df["atr"] = atr(df, cfg.atr_period)
    df["adx"] = adx(df, cfg.adx_period)
    # Filtro trend di fondo: si opera solo nella direzione della EMA lunga.
    use_trend = cfg.ema_trend > 0 and len(df) > cfg.ema_trend
    if use_trend:
        df["ema_trend"] = ema(df["close"], cfg.ema_trend)

    last = df.iloc[-1]
    decision_price = float(last["close"])  # future: usato SOLO per decidere la direzione
    ef, es = float(last["ema_fast"]), float(last["ema_slow"])
    r, a, atr_val = float(last["rsi"]), float(last["adx"]), float(last["atr"])
    et = float(last["ema_trend"]) if use_trend else None

    # Prezzo mostrato all'utente: spot se disponibile, altrimenti future.
    price = spot_price if spot_price is not None else decision_price

    trend_up = (et is None) or (decision_price > et)      # sopra la EMA lunga
    trend_dn = (et is None) or (decision_price < et)      # sotto la EMA lunga
    uptrend = ef > es and decision_price > ef and trend_up
    downtrend = ef < es and decision_price < ef and trend_dn
    trend_strong = a >= cfg.adx_min

    direction, reason = "NO-TRADE", ""
    trend_note = f", allineato al trend EMA{cfg.ema_trend}" if use_trend else ""

    if not trend_strong:
        reason = f"Trend debole (ADX {a:.1f} < {cfg.adx_min:.0f}): mercato laterale, meglio stare fermi."
    elif uptrend and 50 <= r <= 70:
        direction = "LONG"
        reason = f"Uptrend (EMA{cfg.ema_fast}>EMA{cfg.ema_slow}){trend_note}, RSI {r:.1f} in zona momentum, ADX {a:.1f} forte."
    elif downtrend and 30 <= r <= 50:
        direction = "SHORT"
        reason = f"Downtrend (EMA{cfg.ema_fast}<EMA{cfg.ema_slow}){trend_note}, RSI {r:.1f} in zona momentum, ADX {a:.1f} forte."
    else:
        reason = (
            f"Nessun allineamento chiaro (RSI {r:.1f}, EMA fast {ef:.2f} vs slow {es:.2f}). "
            "Momentum non conferma il trend."
        )

    stop_loss = take_profit = rr = None
    if direction == "LONG":
        stop_loss = price - cfg.atr_sl_mult * atr_val
        take_profit = price + cfg.atr_sl_mult * atr_val * cfg.risk_reward
        rr = cfg.risk_reward
    elif direction == "SHORT":
        stop_loss = price + cfg.atr_sl_mult * atr_val
        take_profit = price - cfg.atr_sl_mult * atr_val * cfg.risk_reward
        rr = cfg.risk_reward

    # Punteggio di affidabilita' 0-100 (solo se c'e' un segnale operativo).
    confidence = 0
    if direction in ("LONG", "SHORT"):
        c = min(40.0, max(0.0, a - cfg.adx_min) * 2.0)         # forza del trend (ADX)
        c += 25.0 if use_trend else 12.0                        # allineamento al trend di fondo
        center = 60.0 if direction == "LONG" else 40.0          # centro banda RSI momentum
        c += max(0.0, 20.0 - abs(r - center) * 2.0)             # qualita' momentum
        c += min(15.0, (abs(ef - es) / atr_val if atr_val else 0.0) * 5.0)  # trend definito
        confidence = int(min(100, round(c)))

    return Signal(
        direction=direction,
        price=price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        rr=rr,
        ema_fast=ef,
        ema_slow=es,
        rsi=r,
        adx=a,
        atr=atr_val,
        reason=reason,
        price_is_spot=spot_price is not None,
        decision_price=decision_price,
        confidence=confidence,
    )


def generate_meanrev(df: pd.DataFrame, cfg: Config, spot_price: float | None = None) -> Signal:
    """Strategia MEAN-REVERSION (RSI(2), stile Connors): compra gli eccessi al
    ribasso, vende quelli al rialzo. Sperimentale, per intraday.
    Non tocca la strategia trend dei bot 1/2."""
    df = df.copy()
    df["ema_fast"] = ema(df["close"], cfg.ema_fast)
    df["ema_slow"] = ema(df["close"], cfg.ema_slow)
    df["rsi"] = rsi(df["close"], cfg.rsi_period)
    df["rsi2"] = rsi(df["close"], 2)
    df["adx"] = adx(df, cfg.adx_period)
    df["atr"] = atr(df, cfg.atr_period)

    last = df.iloc[-1]
    decision_price = float(last["close"])
    r2 = float(last["rsi2"])
    atr_val = float(last["atr"])
    price = spot_price if spot_price is not None else decision_price

    direction, reason = "NO-TRADE", ""
    if r2 < 10:
        direction = "LONG"
        reason = f"RSI(2) {r2:.0f} < 10: ipervenduto → rimbalzo atteso (mean-reversion)."
    elif r2 > 90:
        direction = "SHORT"
        reason = f"RSI(2) {r2:.0f} > 90: ipercomprato → ritracciamento atteso (mean-reversion)."
    else:
        reason = f"RSI(2) {r2:.0f}: nessun eccesso da sfruttare."

    stop_loss = take_profit = rr = None
    if direction == "LONG":
        stop_loss = price - cfg.atr_sl_mult * atr_val
        take_profit = price + cfg.atr_sl_mult * atr_val * cfg.risk_reward
        rr = cfg.risk_reward
    elif direction == "SHORT":
        stop_loss = price + cfg.atr_sl_mult * atr_val
        take_profit = price - cfg.atr_sl_mult * atr_val * cfg.risk_reward
        rr = cfg.risk_reward

    # Confidence: piu' l'RSI(2) e' estremo, piu' netto il segnale.
    confidence = 0
    if direction == "LONG":
        confidence = int(min(100, 50 + (10 - r2) * 4))
    elif direction == "SHORT":
        confidence = int(min(100, 50 + (r2 - 90) * 4))

    return Signal(
        direction=direction, price=price, stop_loss=stop_loss, take_profit=take_profit,
        rr=rr, ema_fast=float(last["ema_fast"]), ema_slow=float(last["ema_slow"]),
        rsi=float(last["rsi"]), adx=float(last["adx"]), atr=atr_val, reason=reason,
        price_is_spot=spot_price is not None, decision_price=decision_price, confidence=confidence,
    )


def generate_breakout(df: pd.DataFrame, cfg: Config, spot_price: float | None = None) -> Signal:
    """Strategia BREAKOUT (canale di Donchian): compra la rottura del massimo
    delle ultime N barre, vende la rottura del minimo. Momentum/continuazione.
    Pensata per l'1H (dove il test mostra edge robusto). Sperimentale."""
    df = df.copy()
    N = max(2, int(cfg.donchian_n))
    df["ema_fast"] = ema(df["close"], cfg.ema_fast)
    df["ema_slow"] = ema(df["close"], cfg.ema_slow)
    df["rsi"] = rsi(df["close"], cfg.rsi_period)
    df["adx"] = adx(df, cfg.adx_period)
    df["atr"] = atr(df, cfg.atr_period)
    # Canale: massimo/minimo delle N barre PRECEDENTI (esclusa quella corrente).
    df["hh"] = df["high"].rolling(N).max().shift(1)
    df["ll"] = df["low"].rolling(N).min().shift(1)

    last = df.iloc[-1]
    decision_price = float(last["close"])
    atr_val = float(last["atr"])
    hh, ll = float(last["hh"]), float(last["ll"])
    price = spot_price if spot_price is not None else decision_price

    direction, reason = "NO-TRADE", ""
    if decision_price > hh:
        direction = "LONG"
        reason = f"Breakout rialzista: chiusura sopra il massimo delle ultime {N} barre ({hh:.2f})."
    elif decision_price < ll:
        direction = "SHORT"
        reason = f"Breakout ribassista: chiusura sotto il minimo delle ultime {N} barre ({ll:.2f})."
    else:
        reason = f"Nessuna rottura del canale {N} barre (max {hh:.2f} / min {ll:.2f})."

    stop_loss = take_profit = rr = None
    if direction == "LONG":
        stop_loss = price - cfg.atr_sl_mult * atr_val
        take_profit = price + cfg.atr_sl_mult * atr_val * cfg.risk_reward
        rr = cfg.risk_reward
    elif direction == "SHORT":
        stop_loss = price + cfg.atr_sl_mult * atr_val
        take_profit = price - cfg.atr_sl_mult * atr_val * cfg.risk_reward
        rr = cfg.risk_reward

    # Confidence: piu' l'ADX e' forte, piu' netto il breakout.
    confidence = 0
    if direction in ("LONG", "SHORT"):
        a = float(last["adx"])
        confidence = int(min(100, 45 + max(0.0, a - cfg.adx_min) * 2.5))

    return Signal(
        direction=direction, price=price, stop_loss=stop_loss, take_profit=take_profit,
        rr=rr, ema_fast=float(last["ema_fast"]), ema_slow=float(last["ema_slow"]),
        rsi=float(last["rsi"]), adx=float(last["adx"]), atr=atr_val, reason=reason,
        price_is_spot=spot_price is not None, decision_price=decision_price, confidence=confidence,
    )
