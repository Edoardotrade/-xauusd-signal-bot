"""Verifica le credenziali Capital.com demo ed elenca i conti + l'epic dell'oro.

Uso (sul tuo PC):
  1) nel file .env metti:
        CAPITAL_API_KEY=...
        CAPITAL_IDENTIFIER=la-tua-email
        CAPITAL_PASSWORD=password-della-chiave-API
  2) python capital_accounts.py
"""
from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
BASE = "https://demo-api-capital.backend-capital.com"
key = os.getenv("CAPITAL_API_KEY", "")
ident = os.getenv("CAPITAL_IDENTIFIER", "")
pwd = os.getenv("CAPITAL_PASSWORD", "")
if not (key and ident and pwd):
    raise SystemExit("Metti CAPITAL_API_KEY, CAPITAL_IDENTIFIER e CAPITAL_PASSWORD nel .env.")

r = requests.post(f"{BASE}/api/v1/session",
                  headers={"X-CAP-API-KEY": key, "Content-Type": "application/json"},
                  json={"identifier": ident, "password": pwd}, timeout=20)
if r.status_code >= 300:
    raise SystemExit(f"Login fallito ({r.status_code}): {r.text[:200]}\n"
                     "Controlla che siano credenziali DEMO e la password della chiave API.")
cst, xst = r.headers.get("CST", ""), r.headers.get("X-SECURITY-TOKEN", "")
h = {"X-CAP-API-KEY": key, "CST": cst, "X-SECURITY-TOKEN": xst}

print("Login OK. Conti demo trovati:")
accs = requests.get(f"{BASE}/api/v1/accounts", headers=h, timeout=20).json()
for a in accs.get("accounts", []):
    bal = a.get("balance", {}).get("balance")
    print(f"  - accountId: {a.get('accountId')}  | nome: {a.get('accountName')}  | saldo: {bal}")

try:
    m = requests.get(f"{BASE}/api/v1/markets/GOLD", headers=h, timeout=20).json()
    inst = m.get("instrument", {})
    print(f"\nOro: epic 'GOLD' OK — {inst.get('name')} (min size {m.get('dealingRules', {}).get('minDealSize', {}).get('value')})")
except Exception:
    print("\n(avviso: non ho potuto verificare l'epic 'GOLD', lo controlliamo al test)")

print("\nMetti gli accountId nei secret: CAPITAL_ACCOUNT_ID (bot 1) e CAPITAL_ACCOUNT_ID_2 (bot 2).")
