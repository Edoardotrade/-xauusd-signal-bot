# Bot segnali giornalieri XAUUSD → Telegram

Bot che ogni giorno analizza l'oro (XAUUSD) con una strategia trend-following
(EMA + RSI + ADX + ATR) e invia un avviso su Telegram con direzione, entry,
stop-loss e take-profit.

> ⚠️ **Non è una macchina da soldi.** Nessuna strategia vince sempre. Questo è
> uno strumento di supporto: **prima backtest, poi paper-trading, e solo dopo**
> — se c'è un edge reale — soldi veri. Non è consulenza finanziaria.

---

## Via rapida (consigliata): setup in un comando

1. Su Telegram apri **@BotFather** → `/newbot` → copia il **TOKEN**.
2. Nella cartella del progetto lancia:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```

   Lo script fa tutto: crea l'ambiente, installa le dipendenze, ti chiede il
   token, ricava il chat id da solo, invia un messaggio di prova e (se vuoi)
   pianifica l'invio giornaliero alle 08:00.

Se preferisci i passi manuali, continua qui sotto.

---

## 1. Installazione

```powershell
cd C:\Users\CPrando\xauusd-signal-bot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Crea il bot Telegram

1. Su Telegram apri **@BotFather** → `/newbot` → segui le istruzioni → ricevi il **TOKEN**.
2. Scrivi un messaggio qualsiasi al tuo nuovo bot (così può risponderti).
3. Per il **chat id**: apri **@userinfobot** e leggi il tuo `Id`.
   (In alternativa: visita `https://api.telegram.org/bot<TOKEN>/getUpdates`
   dopo aver scritto al bot, e cerca `"chat":{"id": ...}`.)

## 3. Configura

```powershell
copy .env.example .env
notepad .env   # incolla TOKEN e CHAT_ID
```

> Il file `.env` contiene un segreto: non condividerlo e non caricarlo su GitHub.

## 4. Prova

```powershell
python main.py --dry-run   # stampa il segnale a video, NON invia
python main.py             # invia il segnale su Telegram
```

## 5. Backtest (fallo PRIMA di usarlo per davvero)

```powershell
python backtest.py --period 5y
```

Se l'esito è "NESSUN edge chiaro", **non usare soldi veri**: cambia parametri
nel `.env` (EMA, RSI, ADX_MIN, RISK_REWARD…) e ri-testa, oppure accetta che su
questo timeframe non c'è vantaggio — è un risultato onesto e prezioso.

## 6. Automazione giornaliera (Windows Task Scheduler)

Per riceverlo ogni giorno automaticamente (es. alle 08:00):

```powershell
$py  = "C:\Users\CPrando\xauusd-signal-bot\.venv\Scripts\python.exe"
$job = "C:\Users\CPrando\xauusd-signal-bot\main.py"
schtasks /Create /SC DAILY /ST 08:00 /TN "XAUUSD Signal Bot" `
  /TR "$py $job" /F
```

Per rimuoverlo: `schtasks /Delete /TN "XAUUSD Signal Bot" /F`

---

## Come funziona la strategia

| Componente | Ruolo |
|-----------|-------|
| **EMA 20 vs 50** | direzione del trend (fast sopra slow = rialzista) |
| **RSI 14** | momentum; evita ingressi in zone estreme |
| **ADX 14** | forza del trend; se < 20 → mercato laterale → **NO-TRADE** |
| **ATR 14** | volatilità reale → dimensiona SL e TP (niente numeri arbitrari) |

- **LONG**: uptrend + prezzo sopra EMA fast + RSI 50–70 + ADX ≥ 20
- **SHORT**: downtrend + prezzo sotto EMA fast + RSI 30–50 + ADX ≥ 20
- **NO-TRADE**: tutto il resto (spesso è la scelta giusta)

Stop-loss = `1.5 × ATR`, Take-profit = `1.5 × ATR × RR` (default RR = 2).
Tutto configurabile nel `.env`.

## Note sui dati

`GC=F` (future oro CME) è gratuito e affidabile su Yahoo Finance, molto
correlato allo spot XAUUSD. In alternativa `XAUUSD=X`. Per dati spot più
precisi o intraday servirebbe un data provider dedicato (a pagamento).
```
