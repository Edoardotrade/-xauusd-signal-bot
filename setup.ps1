# Setup guidato del bot segnali XAUUSD.
# Esegui una sola volta:  powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "=== Setup bot segnali XAUUSD ===" -ForegroundColor Cyan

# 1) Virtual environment + dipendenze
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creo l'ambiente virtuale..." -ForegroundColor Yellow
    python -m venv .venv
}
$py = ".\.venv\Scripts\python.exe"
Write-Host "Installo le dipendenze..." -ForegroundColor Yellow
& $py -m pip install --quiet --disable-pip-version-check -r requirements.txt

# 2) File .env
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Creato il file .env." -ForegroundColor Green
}

# 3) Token
$token = Read-Host "Incolla il TOKEN del bot (da @BotFather)"
if ([string]::IsNullOrWhiteSpace($token)) { Write-Host "Nessun token inserito. Riprova." -ForegroundColor Red; exit 1 }
(Get-Content ".env") -replace '^TELEGRAM_BOT_TOKEN=.*', "TELEGRAM_BOT_TOKEN=$token" | Set-Content ".env" -Encoding utf8

Write-Host ""
Write-Host "Ora apri Telegram, cerca il tuo bot e invia un messaggio qualsiasi (es. 'ciao')." -ForegroundColor Cyan
Read-Host "Premi INVIO quando l'hai fatto"

# 4) Chat id automatico
Write-Host "Recupero il chat id..." -ForegroundColor Yellow
& $py get_chat_id.py
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Impossibile recuperare il chat id (vedi errore sopra)." -ForegroundColor Red
    Write-Host "Se il token e' 'non valido (401)': prendi il token NUOVO da @BotFather" -ForegroundColor Red
    Write-Host "(/mybots -> tuo bot -> API Token) e rilancia:  .\setup.ps1" -ForegroundColor Red
    exit 1
}
$chatId = Read-Host "Incolla qui il numero del chat id mostrato sopra"
if ([string]::IsNullOrWhiteSpace($chatId)) { Write-Host "Nessun chat id inserito. Riprova." -ForegroundColor Red; exit 1 }
(Get-Content ".env") -replace '^TELEGRAM_CHAT_ID=.*', "TELEGRAM_CHAT_ID=$chatId" | Set-Content ".env" -Encoding utf8

# 5) Test di invio reale
Write-Host "Invio un messaggio di prova su Telegram..." -ForegroundColor Yellow
& $py main.py

# 6) Pianificazione giornaliera
$ans = Read-Host "Vuoi ricevere il segnale ogni giorno alle 08:00 automaticamente? (s/n)"
if ($ans -eq "s") {
    $job = Join-Path $PSScriptRoot "main.py"
    $pyFull = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    schtasks /Create /SC DAILY /ST 08:00 /TN "XAUUSD Signal Bot" /TR "`"$pyFull`" `"$job`"" /F
    Write-Host "Pianificato! Riceverai il segnale ogni giorno alle 08:00." -ForegroundColor Green
    Write-Host "Per rimuoverlo: schtasks /Delete /TN 'XAUUSD Signal Bot' /F"
}

Write-Host ""
Write-Host "=== Setup completato ===" -ForegroundColor Green
