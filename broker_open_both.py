"""Apre (o chiude) una posizione GOLD di prova su ENTRAMBI i conti demo.
  python broker_open_both.py open   -> apre su conto 1 e conto 2
  python broker_open_both.py close  -> chiude su entrambi
Manda anche una notifica su Telegram con l'esito."""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker

action = sys.argv[1] if len(sys.argv) > 1 else "open"
if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

conti = [("1 (bot conservativo)", os.getenv("CAPITAL_ACCOUNT_ID", "")),
         ("2 (bot aggressivo)", os.getenv("CAPITAL_ACCOUNT_ID_2", ""))]
out = []
for label, acc in conti:
    if not acc:
        out.append(f"Conto {label}: ID mancante (secret non impostato)")
        continue
    os.environ["CAPITAL_ACCOUNT_ID"] = acc  # seleziona questo conto per la prossima chiamata
    r = broker.close_all_gold() if action == "close" else broker.open_test_position()
    out.append(f"Conto {label}: {r}")
    print(out[-1])

# Notifica su Telegram (se configurato).
if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
    try:
        from config import Config
        from telegram_bot import send_message
        cfg = Config.load()
        verbo = "chiuse" if action == "close" else "aperte"
        msg = f"🧪 <b>Posizioni di prova {verbo} sui conti demo</b>\n" + "\n".join(out)
        for c in cfg.chat_ids:
            send_message(cfg.telegram_token, c, msg)
        print("Notifica Telegram inviata.")
    except Exception as exc:  # noqa: BLE001
        print(f"Notifica Telegram non inviata: {exc}")

raise SystemExit(0 if any("OK" in o for o in out) else 1)
