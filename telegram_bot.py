"""Invio messaggi su Telegram tramite la Bot API (solo HTTP, nessuna dipendenza pesante)."""
from __future__ import annotations

import html

import requests

from strategy import Signal

_EMOJI = {"LONG": "🟢", "SHORT": "🔴", "NO-TRADE": "⚪️"}


def format_message(symbol: str, sig: Signal, date_str: str, timeframe: str = "Daily") -> str:
    emoji = _EMOJI.get(sig.direction, "⚪️")
    prezzo_label = "Prezzo spot XAUUSD" if sig.price_is_spot else "Prezzo (future GC=F)"
    lines = [
        f"{emoji} <b>Segnale XAUUSD ({html.escape(timeframe)})</b> — {date_str}",
        "",
        f"<b>Direzione:</b> {sig.direction}",
        f"<b>{prezzo_label}:</b> {sig.price:.2f}",
    ]
    if sig.direction in ("LONG", "SHORT"):
        lines += [
            f"<b>Entry:</b> {sig.price:.2f}",
            f"<b>Stop Loss:</b> {sig.stop_loss:.2f}",
            f"<b>Take Profit:</b> {sig.take_profit:.2f}",
            f"<b>Rischio/Rendimento:</b> 1:{sig.rr:.1f}",
        ]
    lines += [
        "",
        "<b>Indicatori:</b>",
        f"• EMA fast/slow: {sig.ema_fast:.2f} / {sig.ema_slow:.2f}",
        f"• RSI: {sig.rsi:.1f}",
        f"• ADX: {sig.adx:.1f}",
        f"• ATR (volatilità): {sig.atr:.2f}",
        "",
        f"<i>{html.escape(sig.reason)}</i>",
        "",
        "<i>Direzione calcolata sullo storico del future (GC=F); "
        "prezzo e livelli in spot XAUUSD.</i>",
        "",
        "⚠️ <b>Non è consulenza finanziaria.</b> Segnale automatico a scopo "
        "informativo. Fai sempre le tue verifiche e gestisci il rischio.",
    ]
    return "\n".join(lines)


def send_message(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=30,
    )
    payload = resp.json()
    if not payload.get("ok"):
        desc = payload.get("description", "nessuna descrizione")
        hint = ""
        if "chat not found" in desc.lower():
            hint = (
                "\n>> Il TELEGRAM_CHAT_ID nel file .env e' sbagliato o vuoto. "
                "Manda 'ciao' al TUO bot e lancia:  python get_chat_id.py"
            )
        raise RuntimeError(f"Telegram ha rifiutato il messaggio (400): {desc}{hint}")
