"""Ricava automaticamente il tuo TELEGRAM_CHAT_ID.

Prerequisito: aver messo TELEGRAM_BOT_TOKEN nel file .env e aver inviato
ALMENO un messaggio qualsiasi al tuo bot su Telegram.

Uso:
    python get_chat_id.py
"""
from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not token or token == "123456789:ABCdefGhIJKlmNoPQRsTUVwxyz":
    raise SystemExit("Metti prima il TELEGRAM_BOT_TOKEN reale nel file .env.")

resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30)
if resp.status_code == 401:
    raise SystemExit("Token non valido (401). Controlla TELEGRAM_BOT_TOKEN nel file .env.")
data = resp.json()

if not data.get("ok"):
    raise SystemExit(f"Telegram ha risposto con errore: {data}")

updates = data.get("result", [])
if not updates:
    raise SystemExit(
        "Nessun messaggio trovato.\n"
        "1) Apri Telegram, cerca il tuo bot e invia un messaggio qualsiasi (es. 'ciao').\n"
        "2) Ri-esegui: python get_chat_id.py"
    )

chats: dict[int, str] = {}
for upd in updates:
    msg = upd.get("message") or upd.get("channel_post") or {}
    chat = msg.get("chat") or {}
    if "id" in chat:
        name = chat.get("title") or chat.get("username") or chat.get("first_name") or "?"
        chats[chat["id"]] = name

if not chats:
    raise SystemExit("Trovati aggiornamenti ma nessuna chat. Invia un messaggio al bot e riprova.")

print("Chat id trovati:")
for cid, name in chats.items():
    print(f"  {cid}   ({name})")
print()

# Se c'è una sola chat, la salviamo automaticamente nel file .env.
if len(chats) == 1:
    chat_id = str(next(iter(chats)))
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        found = False
        for i, line in enumerate(lines):
            if line.startswith("TELEGRAM_CHAT_ID="):
                lines[i] = f"TELEGRAM_CHAT_ID={chat_id}\n"
                found = True
                break
        if not found:
            lines.append(f"TELEGRAM_CHAT_ID={chat_id}\n")
        with open(env_path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
        print(f"Salvato automaticamente TELEGRAM_CHAT_ID={chat_id} nel file .env.")
    print("\nOra puoi lanciare:  python main.py   (invia il segnale su Telegram)")
else:
    print("Ho trovato piu' chat: copia quello giusto in TELEGRAM_CHAT_ID nel file .env.")
