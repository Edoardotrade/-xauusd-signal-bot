"""Entry point: scarica i dati, genera il segnale, lo invia su Telegram.

Uso:
    python main.py                          # segnale giornaliero (Daily)
    python main.py --interval 1h            # segnale orario (1H)
    python main.py --interval 1h --only-signals   # invia solo se LONG/SHORT (no NO-TRADE)
    python main.py --dry-run                # stampa senza inviare su Telegram
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

# Su Windows la console usa cp1252 e va in crash sugli emoji: forziamo UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config import Config
from data import fetch_ohlc, fetch_spot_price
from journal import record, update_open
from market import is_market_open
from state import already_sent, day_count, day_incr, mark_sent
from strategy import Signal, generate
from telegram_bot import format_message, send_message

# Etichetta leggibile del timeframe per il messaggio.
_TF_LABEL = {"1d": "Daily", "4h": "4H", "1h": "1H", "60m": "1H", "30m": "30M", "15m": "15M"}

# Tetto di segnali al giorno per timeframe (giorni attivi -> ~10 in totale).
# Override globale opzionale con la variabile MAX_SIGNALS_PER_DAY.
_DAILY_CAP = {"Daily": 1, "4H": 2, "1H": 3, "15M": 4, "30M": 4}


def _broadcast(cfg: Config, message: str) -> int:
    """Invia un messaggio a tutti i destinatari. Ritorna quanti l'hanno ricevuto."""
    inviati = 0
    for chat_id in cfg.chat_ids:
        try:
            send_message(cfg.telegram_token, chat_id, message)
            inviati += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠️ destinatario non raggiunto -> {chat_id}: {exc}", file=sys.stderr)
    return inviati


def run_test() -> int:
    """Invia un MESSAGGIO DI PROVA con il formato completo (entry/SL/TP/size/stelle)."""
    cfg = Config.load()
    df = fetch_ohlc(cfg.symbol, interval="1d")
    spot = fetch_spot_price()
    sig = generate(df, cfg, spot_price=spot)
    # Se ora non c'è un vero segnale, costruiamo un esempio LONG solo per la prova.
    if sig.direction == "NO-TRADE":
        entry = sig.price
        sig = Signal(
            direction="LONG", price=entry,
            stop_loss=entry - cfg.atr_sl_mult * sig.atr,
            take_profit=entry + cfg.atr_sl_mult * sig.atr * cfg.risk_reward,
            rr=cfg.risk_reward, ema_fast=sig.ema_fast, ema_slow=sig.ema_slow,
            rsi=sig.rsi, adx=sig.adx, atr=sig.atr,
            reason="MESSAGGIO DI PROVA — esempio di segnale, NON operativo.",
            price_is_spot=sig.price_is_spot, decision_price=sig.decision_price, confidence=72,
        )
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    body = format_message(cfg.symbol, sig, date_str, timeframe="Daily",
                          balance=cfg.account_balance, risk_perc=cfg.risk_perc)
    label = os.getenv("PROFILE_LABEL", "").strip()
    head = (f"⚡ <b>{label}</b>\n" if label else "")
    message = head + "🧪 <b>MESSAGGIO DI PROVA</b> — verifica del bot, non un segnale reale.\n\n" + body
    inviati = _broadcast(cfg, message)
    print(f"Messaggio di prova inviato a {inviati}/{len(cfg.chat_ids)} destinatari.")
    return 0 if inviati > 0 else 1


def run(interval: str = "1d", only_signals: bool = False, dry_run: bool = False,
        force: bool = False) -> int:
    cfg = Config.load()
    tf_label = _TF_LABEL.get(interval, interval)

    # Consapevolezza orari di mercato: niente segnali su dati vecchi a mercato chiuso.
    open_, motivo = is_market_open()
    if not open_ and not force:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"[{ts}] Mercato chiuso: {motivo} Nessun invio. (usa --force per forzare)")
        return 0

    df = fetch_ohlc(cfg.symbol, interval=interval)
    spot = fetch_spot_price()  # spot XAUUSD corrente (None se la fonte non risponde)
    sig = generate(df, cfg, spot_price=spot)
    bar_time = df.index[-1].strftime("%Y-%m-%d %H:%M:%S")  # candela di riferimento

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = format_message(cfg.symbol, sig, date_str, timeframe=tf_label,
                             balance=cfg.account_balance, risk_perc=cfg.risk_perc)
    label = os.getenv("PROFILE_LABEL", "").strip()
    if label:
        message = f"⚡ <b>{label}</b>\n" + message

    # Registro paper-trading + capire se e' un SETUP NUOVO (record() ritorna
    # False se c'e' gia' un trade aperto o e' la stessa barra -> niente ri-invio).
    is_new_setup = True
    if not dry_run:
        update_open(tf_label, df)
        if sig.direction in ("LONG", "SHORT"):
            dist = cfg.atr_sl_mult * sig.atr
            entry_ref = sig.decision_price
            if sig.direction == "LONG":
                sl_ref, tp_ref = entry_ref - dist, entry_ref + dist * cfg.risk_reward
            else:
                sl_ref, tp_ref = entry_ref + dist, entry_ref - dist * cfg.risk_reward
            is_new_setup = record(tf_label, bar_time, sig.direction, entry_ref, sl_ref, tp_ref, cfg.risk_reward)

    # Un solo avviso per setup: se il segnale e' ancora quello in corso, non ri-mandare.
    if sig.direction in ("LONG", "SHORT") and not is_new_setup:
        print(f"[{date_str}] {tf_label}: setup {sig.direction} gia' in corso, nessun nuovo invio.")
        return 0

    # NO-TRADE sugli intraday: non inviare.
    if only_signals and sig.direction == "NO-TRADE":
        print(f"[{date_str}] {tf_label}: NO-TRADE, nessun invio (--only-signals).")
        return 0

    if dry_run:
        print(message.replace("<b>", "").replace("</b>", "")
              .replace("<i>", "").replace("</i>", "")
              .replace("<code>", "").replace("</code>", ""))
        return 0

    # Guardia anti-doppione: se questa barra e' gia' stata inviata, salta.
    if already_sent(tf_label, bar_time):
        print(f"[{date_str}] {tf_label}: gia' inviato per la barra {bar_time}, salto.")
        return 0

    # Tetto di segnali al giorno per timeframe (per_tf di default, override globale via env).
    _env_cap = os.getenv("MAX_SIGNALS_PER_DAY")
    max_day = int(_env_cap) if _env_cap else _DAILY_CAP.get(tf_label, 4)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if sig.direction in ("LONG", "SHORT") and day_count(tf_label, today) >= max_day:
        print(f"[{date_str}] {tf_label}: raggiunto il massimo di {max_day} segnali oggi, salto.")
        return 0

    # Esecuzione automatica su conto DEMO OANDA (se configurato e prezzi in spot).
    if sig.direction in ("LONG", "SHORT") and sig.price_is_spot:
        try:
            import broker
            if broker.enabled():
                esito = broker.execute_if_flat(sig.direction, sig.price, sig.stop_loss,
                                                sig.take_profit, cfg.risk_perc)
                print(f"[{date_str}] {tf_label}: OANDA demo -> {esito}")
        except Exception as exc:  # noqa: BLE001 - l'esecuzione ko non blocca l'avviso
            print(f"[{date_str}] {tf_label}: errore esecutore OANDA -> {exc}", file=sys.stderr)

    inviati, errori = 0, []
    for chat_id in cfg.chat_ids:
        try:
            send_message(cfg.telegram_token, chat_id, message)
            inviati += 1
        except Exception as exc:  # noqa: BLE001 - un destinatario ko non blocca gli altri
            errori.append(f"{chat_id}: {exc}")
    if inviati > 0:
        mark_sent(tf_label, bar_time)
        if sig.direction in ("LONG", "SHORT"):
            day_incr(tf_label, today)
    print(f"[{date_str}] {tf_label}: {sig.direction} @ {sig.price:.2f} — inviato a {inviati}/{len(cfg.chat_ids)} destinatari.")
    for err in errori:
        print(f"  ⚠️ destinatario non raggiunto -> {err}", file=sys.stderr)
    # Fallisce solo se NESSUNO ha ricevuto (cosi' GitHub segnala l'errore).
    return 0 if inviati > 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot segnali XAUUSD → Telegram")
    parser.add_argument("--interval", default="1d", help="Timeframe: 1d (default) o 1h")
    parser.add_argument("--only-signals", action="store_true",
                        help="Invia solo LONG/SHORT (salta i NO-TRADE). Utile su 1h.")
    parser.add_argument("--dry-run", action="store_true", help="Non invia su Telegram, stampa a video")
    parser.add_argument("--force", action="store_true", help="Invia anche a mercato chiuso (per test)")
    parser.add_argument("--test", action="store_true", help="Invia un MESSAGGIO DI PROVA e termina")
    args = parser.parse_args()
    try:
        if args.test:
            return run_test()
        return run(interval=args.interval, only_signals=args.only_signals,
                   dry_run=args.dry_run, force=args.force)
    except Exception as exc:  # noqa: BLE001 - vogliamo un errore leggibile all'utente
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
