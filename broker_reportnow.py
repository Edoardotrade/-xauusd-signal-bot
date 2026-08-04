"""Invia subito il report del conto demo (saldo, P/L, posizioni) sul canale."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker
from config import Config
from telegram_bot import send_message

if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

rep = broker.account_report()
if not rep:
    print("Report non disponibile.")
    raise SystemExit(1)
print(rep)

cfg = Config.load()
n = 0
for c in cfg.chat_ids:
    try:
        send_message(cfg.telegram_token, c, rep)
        n += 1
    except Exception as exc:  # noqa: BLE001
        print(f"errore invio {c}: {exc}")
print(f"Report inviato a {n} destinatari.")
raise SystemExit(0 if n else 1)
