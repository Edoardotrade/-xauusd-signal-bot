"""Diagnostico: prova l'esecuzione sul conto demo con livelli realistici e
scrive l'esito esatto in diag.txt (per capire perche' un trade non si apre)."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os

import broker
from data import fetch_spot_price

lines = []
lines.append(f"CAPITAL_ACCOUNT_ID usato = {os.getenv('CAPITAL_ACCOUNT_ID', '')!r}")
s = broker.status()
if s:
    for c in s.get("conti", []):
        lines.append(f"  conto trovato: id={c['id']!r} saldo={c['saldo']!r}")
else:
    lines.append("  status() ha fallito (login/lettura conti).")

spot = fetch_spot_price()
lines.append(f"spot (gold-api) = {spot}")

if not spot:
    lines.append("!! spot non disponibile -> price_is_spot=False -> l'esecuzione VIENE SALTATA. "
                 "Ecco perche' l'avviso arriva ma non apre nulla.")
elif not broker.enabled():
    lines.append("!! broker non abilitato (secret Capital mancanti nel workflow).")
else:
    for name, sld, tpd in [("daily-like", 66, 99), ("15m-like", 22, 33), ("stretto-10", 10, 15)]:
        entry = spot
        sl = round(entry - sld, 2)
        tp = round(entry + tpd, 2)
        r = broker.execute("LONG", entry, sl, tp, 1.0)
        lines.append(f"{name} (sl {sld}, tp {tpd}) -> {r}")
    lines.append("cleanup: " + broker.close_all_gold())

out = "\n".join(lines)
print(out)
with open("diag.txt", "w", encoding="utf-8") as f:
    f.write(out + "\n")
