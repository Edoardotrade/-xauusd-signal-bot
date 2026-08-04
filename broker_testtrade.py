"""Esegue un trade di PROVA sul conto demo (apre e richiude subito).
Esce 0 se il giro completo funziona, 1 in caso di errore."""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker

if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

r = broker.test_trade()
print(r)
raise SystemExit(0 if r.startswith("OK") else 1)
