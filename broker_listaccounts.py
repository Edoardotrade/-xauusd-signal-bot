"""Manda sul canale Telegram la lista dei conti demo Capital (per trovare gli ID)."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker
from config import Config
from telegram_bot import send_message

if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

s = broker.status()
if not s:
    print("Connessione fallita.")
    raise SystemExit(1)

righe = ["🏦 <b>I tuoi conti demo Capital.com</b>", ""]
for c in s["conti"]:
    righe.append(f"• ID <code>{c['id']}</code> — saldo {c['saldo']}")
righe += ["",
          "<i>Metti un ID nel secret CAPITAL_ACCOUNT_ID (bot 1) e un ALTRO "
          "ID (diverso) in CAPITAL_ACCOUNT_ID_2 (bot 2). Se ne vedi uno solo, "
          "crea un secondo conto demo nell'app.</i>"]
testo = "\n".join(righe)

cfg = Config.load()
inviati = 0
for chat_id in cfg.chat_ids:
    try:
        send_message(cfg.telegram_token, chat_id, testo)
        inviati += 1
    except Exception as exc:  # noqa: BLE001
        print(f"errore invio {chat_id}: {exc}")
print(f"Lista conti inviata a {inviati} destinatari.")
raise SystemExit(0 if inviati else 1)
