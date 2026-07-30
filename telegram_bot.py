"""Invio messaggi su Telegram tramite la Bot API (solo HTTP, nessuna dipendenza pesante)."""
from __future__ import annotations

import html

import requests

from strategy import Signal

_EMOJI = {"LONG": "🟢", "SHORT": "🔴", "NO-TRADE": "⚪️"}
_CONTRACT_OZ = 100  # XAUUSD: 1 lotto standard = 100 oz -> $100 per ogni $1 di movimento


def _stars(confidence: int) -> str:
    n = max(1, min(5, round(confidence / 20)))
    return "⭐" * n + "☆" * (5 - n)


def _sizing_lines(sig: Signal, balance: float, risk_perc: float) -> list[str]:
    """Blocco gestione del rischio: quanti lotti per rischiare risk_perc% del saldo."""
    sl_dist = abs(sig.price - sig.stop_loss)
    tp_dist = abs(sig.take_profit - sig.price)
    if sl_dist <= 0:
        return []
    risk_eur = balance * risk_perc / 100.0
    lots = risk_eur / (sl_dist * _CONTRACT_OZ)
    profit_eur = lots * tp_dist * _CONTRACT_OZ
    return [
        "",
        f"💰 <b>Gestione rischio (DEMO {balance:,.0f})</b>",
        f"• Rischio {risk_perc:.1f}% = {risk_eur:,.0f} → <b>~{lots:.2f} lotti</b>",
        f"• Distanza SL: {sl_dist:.2f} $ · TP: {tp_dist:.2f} $",
        f"• Se va a target: <b>+{profit_eur:,.0f}</b> · se va a SL: −{risk_eur:,.0f}",
    ]


def format_message(symbol: str, sig: Signal, date_str: str, timeframe: str = "Daily",
                   balance: float = 10000.0, risk_perc: float = 1.0) -> str:
    emoji = _EMOJI.get(sig.direction, "⚪️")
    prezzo_label = "Prezzo spot XAUUSD" if sig.price_is_spot else "Prezzo (future GC=F)"
    lines = [
        f"{emoji} <b>Segnale XAUUSD ({html.escape(timeframe)})</b> — {date_str}",
    ]
    if timeframe != "Daily":
        lines.append("🧪 <b>SPERIMENTALE — NON OPERARE</b> (backtest negativo, solo osservazione)")
    lines += [
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
            f"<b>Affidabilità:</b> {_stars(sig.confidence)} ({sig.confidence}/100)",
        ]
        lines += _sizing_lines(sig, balance, risk_perc)
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
