"""Elenca gli ID dei tuoi conti DEMO OANDA usando il token API practice.

Uso:
  1) metti il token nel file .env come  OANDA_API_TOKEN=xxxxx
     (oppure:  $env:OANDA_API_TOKEN="xxxxx"  in PowerShell)
  2) python oanda_accounts.py
"""
from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
token = os.getenv("OANDA_API_TOKEN", "")
if not token:
    raise SystemExit("Metti prima OANDA_API_TOKEN (nel .env o come variabile d'ambiente).")

r = requests.get(
    "https://api-fxpractice.oanda.com/v3/accounts",
    headers={"Authorization": f"Bearer {token}"},
    timeout=20,
)
if r.status_code == 401:
    raise SystemExit("Token non valido (401). Assicurati sia il token PRACTICE/demo.")
r.raise_for_status()
accounts = r.json().get("accounts", [])
if not accounts:
    raise SystemExit("Nessun conto demo trovato per questo token.")

print("Conti demo trovati (usa due ID diversi per i due bot):")
for a in accounts:
    print("  -", a.get("id"))
print("\nMetti il primo in OANDA_ACCOUNT_ID e il secondo in OANDA_ACCOUNT_ID_2 (secrets GitHub).")
