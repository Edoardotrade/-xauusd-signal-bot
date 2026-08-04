"""Manda su Telegram la mappatura Bot->Conto (con saldo) e chiude le posizioni
di prova su entrambi i conti."""
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker

if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

id1 = os.getenv("CAPITAL_ACCOUNT_ID", "")
id2 = os.getenv("CAPITAL_ACCOUNT_ID_2", "")

# Saldi correnti di tutti i conti.
s = broker.status() or {"conti": []}
saldi = {c["id"]: c["saldo"] for c in s.get("conti", [])}

# Chiude le posizioni di prova su entrambi i conti.
esiti = []
for acc in [id1, id2]:
    if acc:
        os.environ["CAPITAL_ACCOUNT_ID"] = acc
        esiti.append(broker.close_all_gold())

msg = (
    "🔗 <b>Mappatura conti demo</b>\n\n"
    f"🟢 <b>Bot 1 (conservativo)</b> → conto <code>{id1}</code>\n"
    f"   saldo attuale: {saldi.get(id1, '?')} → <b>portalo a 10.000</b>\n\n"
    f"🧪 <b>Bot 2 (aggressivo)</b> → conto <code>{id2}</code>\n"
    f"   saldo attuale: {saldi.get(id2, '?')} → <b>portalo a 3.000</b>\n\n"
    "<i>Nell'app Capital.com: seleziona ogni conto demo e usa "
    "'Reset/Aggiungi fondi' per impostare il saldo. Le posizioni di prova "
    "sono state chiuse.</i>"
)
print(msg)

if os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
    try:
        from config import Config
        from telegram_bot import send_message
        cfg = Config.load()
        for c in cfg.chat_ids:
            send_message(cfg.telegram_token, c, msg)
        print("Mappatura inviata su Telegram.")
    except Exception as exc:  # noqa: BLE001
        print(f"Telegram non inviato: {exc}")
