"""Test di connessione al conto DEMO Capital.com (nessun trade).
Esce 0 se le credenziali funzionano, 1 se falliscono."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker

if not broker.enabled():
    print("Credenziali Capital mancanti (secrets non configurati).")
    raise SystemExit(1)

s = broker.status()
if not s:
    print("Connessione al conto demo FALLITA (controlla i secret / che siano DEMO).")
    raise SystemExit(1)

print("Connessione al conto demo OK.")
for c in s["conti"]:
    print(f"  conto {c['id']} - saldo {c['saldo']}")
