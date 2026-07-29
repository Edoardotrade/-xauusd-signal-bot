"""Entry point: scarica i dati, genera il segnale, lo invia su Telegram.

Uso:
    python main.py            # esegue una volta e invia il segnale del giorno
    python main.py --dry-run  # stampa il segnale senza inviarlo su Telegram
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
from data import fetch_daily, fetch_spot_price
from strategy import generate
from telegram_bot import format_message, send_message


def run(dry_run: bool = False) -> int:
    cfg = Config.load()

    df = fetch_daily(cfg.symbol, period="1y")
    spot = fetch_spot_price()  # spot XAUUSD corrente (None se la fonte non risponde)
    sig = generate(df, cfg, spot_price=spot)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    message = format_message(cfg.symbol, sig, date_str)

    if dry_run:
        # In dry-run stampiamo solo a video (utile per test / backtest visivo).
        print(message.replace("<b>", "").replace("</b>", "")
              .replace("<i>", "").replace("</i>", "")
              .replace("<code>", "").replace("</code>", ""))
        return 0

    send_message(cfg.telegram_token, cfg.telegram_chat_id, message)
    print(f"[{date_str}] Segnale inviato: {sig.direction} @ {sig.price:.2f}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot segnali giornalieri XAUUSD → Telegram")
    parser.add_argument("--dry-run", action="store_true", help="Non invia su Telegram, stampa a video")
    args = parser.parse_args()
    try:
        return run(dry_run=args.dry_run)
    except Exception as exc:  # noqa: BLE001 - vogliamo un errore leggibile all'utente
        print(f"ERRORE: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
