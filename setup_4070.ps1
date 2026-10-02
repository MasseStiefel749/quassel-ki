# Setup für den Haupt-Rechner (RTX 4070) - Quassel-KI v17 portieren
# 1. Dieses Repo klonen bzw. den Ordner "quassel-ki" per USB/Cloud auf den neuen PC kopieren, z.B. nach:
#    C:\Users\DEINNAME\Documents\Default Project\quassel-ki
# 2. Ollama installieren (https://ollama.com/download) und starten
# 3. Dieses Skript per Rechtsklick "Mit PowerShell ausführen"
$ErrorActionPreference = "Stop"
$QDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "== Quassel-KI Setup (4070) in $QDir =="

python --version
pip install -r (Join-Path $QDir "requirements.txt")

ollama serve 2>$null | Out-Null
Start-Sleep -Seconds 2
if (-not (Get-Process -Name "ollama" -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
  Start-Sleep -Seconds 5
}
# Schlaustes Game-Creation-Modell das auf 12GB VRAM läuft:
# Versuch 1: qwen3-coder:30b (MoE, top Coding + Reasoning, ~19GB). Fallback: qwen2.5-coder:32b.
$BaseModel = "qwen2.5-coder:32b"
ollama pull qwen3-coder:30b
if ($?) { $BaseModel = "qwen3-coder:30b" } else { ollama pull qwen2.5-coder:32b }
# Seh-Modell für Bildschirm (1.7GB):
ollama pull moondream
# Quassel-Persönlichkeit bauen (auf dem gewählten Basis-Modell):
$Modelfile = Join-Path $QDir "ollama-model\Modelfile"
(Get-Content $Modelfile) -replace '^FROM .*', "FROM $BaseModel" | Set-Content "$Modelfile.4070"
ollama create quassel-ki -f "$Modelfile.4070"
ollama list
Write-Host ""
Write-Host "Fertig! Start mit:"
Write-Host "  python `"$QDir\quassel_ki_v17.py`"   (oder .\start.ps1)"
Write-Host "Hinweis 4070: Ollama lagert automatisch aus (ca. 12GB VRAM + Rest RAM). Falls langsam: OLLAMA_NUM_PARALLEL=1 setzen."
