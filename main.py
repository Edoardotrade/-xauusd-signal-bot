"""Entry point: scarica i dati, genera il segnale, lo invia su Telegram.

Uso:
    python main.py                          # segnale giornaliero (Daily)
    python main.py --interval 1h            # segnale orario (1H)
    python main.py --interval 1h --only-signals   # invia solo se LONG/SHORT (no NO-TRADE)
    python main.py --dry-run                # stampa senza inviare su Telegram
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

# Su Windows la console usa cp1252 e va in crash sugli emoji: forziamo UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from config import Config
from data import fetch_ohlc, fetch_spot_price
from market import is_market_open
from strategy import generate
from telegram_bot import format_message, send_message

# Etichetta leggibile del timeframe per il messaggio.
_TF_LABEL = {"1d": "Daily", "1h": "1H", "60m": "1H", "30m": "30M", "15m": "15M"}


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

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = format_message(cfg.symbol, sig, date_str, timeframe=tf_label)

    # Anti-spam (utile su 1h): se richiesto, non inviare i NO-TRADE.
    if only_signals and sig.direction == "NO-TRADE":
        print(f"[{date_str}] {tf_label}: NO-TRADE, nessun invio (--only-signals).")
        return 0

    if dry_run:
        print(message.replace("<b>", "").replace("</b>", "")
              .replace("<i>", "").replace("</i>", "")
              .replace("<code>", "").replace("</code>", ""))
        return 0

    inviati, errori = 0, []
    for chat_id in cfg.chat_ids:
        try:
            send_message(cfg.telegram_token, chat_id, message)
            inviati += 1
        except Exception as exc:  # noqa: BLE001 - un destinatario ko non blocca gli altri
            errori.append(f"{chat_id}: {exc}")
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
    args = parser.parse_args()
    try:
        return run(interval=args.interval, only_signals=args.only_signals,
                   dry_run=args.dry_run, force=args.force)
    except Exception as exc:  # noqa: BLE001 - vogliamo un errore leggibile all'utente
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
