"""Trova gli ID di chat/canali dove il bot ha ricevuto messaggi (via getUpdates)
e li manda alla chat privata dell'utente, per trovare l'ID di un nuovo canale."""
import os
import sys

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

token = os.getenv("TELEGRAM_BOT_TOKEN", "")
priv = os.getenv("PRIVATE_CHAT_ID", "6710333146")
if not token:
    raise SystemExit("TELEGRAM_BOT_TOKEN mancante.")

r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
chats = {}
for u in r.get("result", []):
    m = u.get("message") or u.get("channel_post") or u.get("my_chat_member") or {}
    c = m.get("chat", {})
    if "id" in c:
        chats[c["id"]] = f"{c.get('title') or c.get('first_name') or c.get('username') or '?'} ({c.get('type')})"

lines = ["🔎 <b>Chat e canali trovati</b>", ""]
for k, v in chats.items():
    lines.append(f"• <code>{k}</code> — {v}")
lines += ["", "<i>L'ID del NUOVO canale inizia con -100. Mettilo nel secret "
          "TELEGRAM_CHAT_ID_3.</i>"]
msg = "\n".join(lines)
print(msg)

requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
              json={"chat_id": priv, "text": msg, "parse_mode": "HTML"}, timeout=20)
print("Inviato alla chat privata.")
