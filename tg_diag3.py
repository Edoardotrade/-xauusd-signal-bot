"""Diagnostica l'invio al canale 3: prova a scrivere e riporta l'errore ESATTO
alla chat privata (cosi' capiamo se e' ID sbagliato o bot non admin)."""
import os
import sys

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
ch3 = os.getenv("TELEGRAM_CHAT_ID_3", "")
priv = os.getenv("PRIVATE_CHAT_ID", "6710333146")


def send(chat, text):
    return requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                         json={"chat_id": chat, "text": text}, timeout=20).json()


res = send(ch3, "✅ Se leggi questo, il canale 3 è collegato correttamente.")
if res.get("ok"):
    esito = f"Canale 3 OK (id {ch3})."
else:
    esito = (f"❌ Canale 3 NON funziona.\nID nel secret: {ch3!r}\n"
             f"Errore Telegram: {res.get('description')}\n\n"
             "Se dice 'chat not found' → ID sbagliato. Se dice 'not enough rights' "
             "o 'not a member' → il bot non è amministratore del canale.")
print(esito)
send(priv, "🔧 Diagnostica canale 3:\n" + esito)
