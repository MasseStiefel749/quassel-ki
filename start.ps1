# Quassel-KI starten (ein Klick): prüft Ollama, dann ab die Post
$ErrorActionPreference = "Stop"
$QDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $QDir

if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
  Write-Host "Starte Ollama..."
  Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
  Start-Sleep -Seconds 5
}
try {
  $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
  $namen = @($tags.models | ForEach-Object { $_.name })
  if ($namen -notcontains "quassel-ki:latest") {
    Write-Host "Baue quassel-ki Modell (dauert beim 1. Mal)..."
    & ollama create quassel-ki -f (Join-Path $QDir "ollama-model\Modelfile")
  }
  Write-Host "Modelle: $($namen -join ', ')"
} catch {
  Write-Host "Ollama antwortet nicht auf :11434 - trotzdem starten? (Enter)" -ForegroundColor Yellow
  Read-Host
}
# Stimme aus bei aktivem Teams-Call
$calls = Get-Process -Name "ms-teams" -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -match "Anruf|Call|Besprechung|Meeting" }
if ($calls -and -not $env:QUASSEL_VOICE) { $env:QUASSEL_VOICE = "0"; Write-Host "Teams-Call erkannt -> Stimme aus." }

Write-Host "Starte quassel_ki_v20.py ..."
Start-Process python "quassel_ki_v20.py" -WorkingDirectory $QDir
Write-Host "Läuft. Fenster kann zu."
