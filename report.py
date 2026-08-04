"""Invia su Telegram il report del paper-trading (win rate reale, R totale).

Uso:
    python report.py            # invia il riepilogo ai destinatari
    python report.py --dry-run  # stampa senza inviare
"""
from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import Config
from journal import recent_closed_text, summary_text
from telegram_bot import send_message


def main() -> int:
    parser = argparse.ArgumentParser(description="Report paper-trading XAUUSD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        testo = summary_text() + "\n\n" + recent_closed_text(10)
        print(testo.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")
              .replace("&gt;", ">"))
        return 0

    cfg = Config.load()
    testo = summary_text(risk_perc=cfg.risk_perc) + "\n\n" + recent_closed_text(10)
    inviati = 0
    for chat_id in cfg.chat_ids:
        try:
            send_message(cfg.telegram_token, chat_id, testo)
            inviati += 1
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ {chat_id}: {exc}", file=sys.stderr)
    print(f"Report inviato a {inviati}/{len(cfg.chat_ids)} destinatari.")
    return 0 if inviati > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
