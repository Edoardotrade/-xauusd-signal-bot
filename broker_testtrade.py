"""Esegue un trade di PROVA sul conto demo (apre e richiude subito) e manda
un messaggio su Telegram con l'esito. Esce 0 se il giro funziona, 1 se no."""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker

if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

r = broker.test_trade()
print(r)

# Notifica su Telegram (se configurato).
if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
    try:
        from config import Config
        from telegram_bot import send_message
        cfg = Config.load()
        testo = ("🧪 <b>TEST esecuzione demo</b>\n"
                 f"Esito: {r}\n\n"
                 "<i>Trade di prova sull'oro: aperto e richiuso subito sul conto demo, "
                 "solo per verificare che l'apertura automatica funzioni.</i>")
        for chat_id in cfg.chat_ids:
            send_message(cfg.telegram_token, chat_id, testo)
        print("Notifica Telegram inviata.")
    except Exception as exc:  # noqa: BLE001
        print(f"Notifica Telegram non inviata: {exc}")

raise SystemExit(0 if r.startswith("OK") else 1)
