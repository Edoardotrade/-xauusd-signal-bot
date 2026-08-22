"""Avvisi eventi/news per l'oro: agenda del mattino + heads-up pre-evento.

NON prevede il prezzo. Avvisa solo della volatilita' in arrivo (gestione rischio).
Chiamato dal motore (tick) e usabile a mano:
    python news.py --agenda     # invia l'agenda di oggi ai destinatari
    python news.py --dry-run    # stampa l'agenda senza inviare
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import events
from config import Config
from state import news_mark, news_seen
from telegram_bot import send_message

HEADSUP_MIN = 35   # avvisa ~35 minuti prima dell'evento
AGENDA_HOUR = 7    # ora UTC dell'agenda giornaliera


def _broadcast(cfg: Config, text: str) -> int:
    n = 0
    for chat_id in cfg.chat_ids:
        try:
            send_message(cfg.telegram_token, chat_id, text)
            n += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ⚠️ {chat_id}: {exc}", file=sys.stderr)
    return n


def tick(now: datetime | None = None) -> None:
    """Chiamato ogni minuto dal motore: agenda alle 07:00 UTC + heads-up eventi."""
    now = now or datetime.now(timezone.utc)
    cfg = Config.load()

    # Agenda giornaliera (una volta, alle 07:00 UTC).
    if now.hour == AGENDA_HOUR and now.minute == 0:
        akey = "AGENDA-" + now.strftime("%Y-%m-%d")
        if not news_seen(akey):
            _broadcast(cfg, events.format_agenda(events.today_events(now)))
            news_mark(akey)

    # Heads-up: eventi che partono entro ~35 minuti (una volta per evento).
    for e in events.upcoming(HEADSUP_MIN, now):
        if not news_seen(e["key"]):
            _broadcast(cfg, events.format_headsup(e))
            news_mark(e["key"])

    # Report giornaliero del conto demo (una volta, alle 20:00 UTC).
    if now.hour == 20 and now.minute == 0:
        rkey = "ACCTREPORT-" + now.strftime("%Y-%m-%d")
        if not news_seen(rkey):
            try:
                import broker
                if broker.enabled():
                    rep = broker.account_report()
                    if rep:
                        _broadcast(cfg, rep)
            except Exception as exc:  # noqa: BLE001
                print(f"[news] report conto ko: {exc}")
            news_mark(rkey)

    # Report giornaliero del WIN RATE (una volta, alle 20:05 UTC).
    if now.hour == 20 and now.minute == 5:
        wkey = "WINRATE-" + now.strftime("%Y-%m-%d")
        if not news_seen(wkey):
            try:
                from journal import summary_text, recent_closed_text
                msg = ("📅 <b>Riepilogo giornaliero</b>\n\n" + summary_text(cfg.risk_perc, cfg.account_balance)
                       + "\n\n" + recent_closed_text(10))
                _broadcast(cfg, msg)
            except Exception as exc:  # noqa: BLE001
                print(f"[news] report winrate ko: {exc}")
            news_mark(wkey)


def main() -> int:
    p = argparse.ArgumentParser(description="Avvisi eventi/news oro")
    p.add_argument("--agenda", action="store_true", help="Invia l'agenda di oggi")
    p.add_argument("--dry-run", action="store_true", help="Stampa senza inviare")
    args = p.parse_args()

    txt = events.format_agenda(events.today_events())
    if args.dry_run:
        print(txt.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
        return 0
    if args.agenda:
        cfg = Config.load()
        n = _broadcast(cfg, txt)
        print(f"Agenda inviata a {n}/{len(cfg.chat_ids)} destinatari.")
        return 0 if n > 0 else 1
    print("Usa --agenda per inviare o --dry-run per vedere l'anteprima.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
