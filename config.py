"""Configurazione centralizzata: legge le variabili dal file .env."""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _get(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    telegram_token: str
    telegram_chat_id: str
    symbol: str
    ema_fast: int
    ema_slow: int
    ema_trend: int
    rsi_period: int
    atr_period: int
    adx_period: int
    adx_min: float
    risk_reward: float
    atr_sl_mult: float

    @property
    def chat_ids(self) -> list[str]:
        """Lista dei destinatari: TELEGRAM_CHAT_ID puo' contenere piu' id
        separati da virgola (es. '111,222') per inviare a piu' persone."""
        return [c.strip() for c in self.telegram_chat_id.split(",") if c.strip()]

    @classmethod
    def load(cls) -> "Config":
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat_id:
            raise SystemExit(
                "ERRORE: TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID mancanti.\n"
                "Copia .env.example in .env e compila i valori. Vedi il README."
            )
        return cls(
            telegram_token=token,
            telegram_chat_id=chat_id,
            symbol=_get("SYMBOL", "GC=F"),
            ema_fast=int(_get("EMA_FAST", "20")),
            ema_slow=int(_get("EMA_SLOW", "50")),
            ema_trend=int(_get("EMA_TREND", "200")),   # filtro trend di fondo (0 = disattivo)
            rsi_period=int(_get("RSI_PERIOD", "14")),
            atr_period=int(_get("ATR_PERIOD", "14")),
            adx_period=int(_get("ADX_PERIOD", "14")),
            adx_min=float(_get("ADX_MIN", "20")),
            risk_reward=float(_get("RISK_REWARD", "1.5")),   # 1:1.5 -> win rate piu' alto, stesso profitto
            atr_sl_mult=float(_get("ATR_SL_MULT", "1.5")),
        )
