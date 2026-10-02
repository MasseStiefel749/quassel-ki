# Architektur aktuell (v19, Stand 02.10.2026, BESTÄTIGT per Code-Inspektion + Tests)

## Einstiegspunkt

- `quassel_ki_v19.py` (3143 Zeilen, Tkinter-App, Klasse `QuasselKI`).
  Start: `.\start.ps1` oder `python quassel_ki_v19.py`. Ältere Dateien
  `quassel_ki_v17.py` / `v18.py` liegen noch im Root (nicht aktiv).
- `quassel/`-Paket (v18/v19-Module, getestet): `hardware`, `modelle`
  (Brain-Router), `memory2` (typisiertes Memory), `konfig` (yaml),
  `projekte` (Scanner + Task-Discovery).
- `quassel.yaml`: Rollen, Speed, Memory, Agent, Projekte, Safety.
- `quassel_benchmark.py`: echte Messwerte → `logs/benchmark_*.json`.

## Module

| Modul | Aufgabe | Test |
|---|---|---|
| `hardware` | GPU/VRAM/RAM/CPU/Ollama-Modelle, `profil_text()` | test_v18 (Struktur) |
| `modelle` | Difficulty TRIVIAL–MAX, Rollen fast/coding/reasoning/vision/fallback, Speed-Modes, `context_budget()` | test_v18 (Logik) |
| `memory2` | typisierte Einträge (Typ/Quelle/Confidence), Migration, Retrieval, Ablauf-Markierung | test_v18 |
| `konfig` | yaml laden + Defaults mergen | test_v18 |
| `projekte` | Scan (nur konfigurierte Pfade), Typ-Erkennung, Doku-Suche, TODO-Extraktion DE/EN, Confidence+Risk, Ranking | test_v19 (10 Tests, Fixture-Baum) |

App-Kern: Ask (Stream) / Agent (Tool-Loop, max 8 Runden) / Live (Vision+Maus)
/ Tools-Tab / Forge (Gerüst, Batch, Tasks, Git, Checks, Impact, Log).
37 Chat-Befehle (`/scan`, `/finish`, `/stumm`, `/speed`, …), 10 Skills,
Plugin-Hot-Reload, 31 Tool-Zweige im MCP-Client.

## Speicher

| Datei | Inhalt | Stand 02.10. |
|---|---|---|
| `memory.json` | flache Fakten-Strings (legacy) | **leer**, wird parallel weiter befüllt |
| `memory2.json` | typisierte Einträge | 2 Einträge |
| `zusammenfassung.json` | Rolling Summary | aktiv |
| `erinnerungen.json` | Episoden Q/A | 1 Eintrag, wird gespeichert aber **nicht gelesen** |
| `projekt_index.json` | alter Datei-Index | veraltet, Nachfolger unten |
| `projekt_index_v19.json` | Projekt-Scans (10 Projekte) | aktiv |
| `chats/*.json` | volle Verläufe | wachsen unbegrenzt (Dedup fehlt) |

Doppelt/veraltet: `memory.json` ↔ `memory2.json`, `projekt_index.json` ↔
`projekt_index_v19.json`. `erinnerungen.json` ist schreibend tot (nie gelesen).

## Tools

~35 lokale Tools (Datei, Git, UE-Doku, Forge, Vision, System). Kein natives
Ollama-Tool-Calling – Agent parst ```action-JSON-Blöcke (fragil, aber mit
Tests abgesichert). Build/Test-Adapter für UE (UAT/UBT) fehlt. `/logcheck`
zeigt Logtext, keine konkreten nächsten Schritte. `/impact` nur
Text-Suche, keine Modul-/Asset-Graphen.

## Sicherheitsmodell

Lesen=Standard; Schreiben/Ausführen → Permit (lesen/auto/voll) + Blockliste
+ Diff-Vorschau + `aktionen.log`. Find&Finish: nur Confidence ≥0.8 +
Risiko LOW/MEDIUM, Git-Checkpoint-Branch pro Task, kein Auto-Push.
Stops: STUMM (nur Stimme), QUASSELN-STOP (nur Spontanes), AGENT-STOP
(keine neuen Tools + Autosave), STOP-ALLES (Not-Aus). Live: Fail-Safe
(Maus-Ecke), Klicks nur mit Nachfrage.

## Tests

`tests/test_v18.py` (17) + `tests/test_v19.py` (10) = **27/27 BESTÄTIGT**
grün am 02.10.2026. Kein UI-Test, kein E2E-Agent-Test, kein Benchmark-Test.
