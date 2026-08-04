"""Apre o chiude una posizione GOLD di prova sul demo.
  python broker_manage.py open   -> apre una posizione visibile
  python broker_manage.py close  -> chiude tutte le posizioni GOLD
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import broker

action = sys.argv[1] if len(sys.argv) > 1 else "open"
if not broker.enabled():
    print("Credenziali Capital mancanti.")
    raise SystemExit(1)

r = broker.close_all_gold() if action == "close" else broker.open_test_position()
print(r)
raise SystemExit(0 if r.startswith("OK") else 1)
