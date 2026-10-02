# ❯ Quassel-KI – lokaler AI Game Development Assistant

Lokaler **AI Game Development Assistant** für Unreal Engine (UE 5.8) – läuft komplett **offline** auf dem eigenen PC: kein Cloud-Abo, keine Daten gehen raus, kein Auto-Push, kein Tracking.

**Stand: v20** (76/76 Tests grün) – Brain-Router, Hardware-Profile, Memory 2.0, Unreal-Scanner, tasks.json, Build/Test-Adapter, Impact-Schutz, Find&Finish-Loop.

## Was sie kann

- **Reden & Arbeiten:** Ask-Modus (nur antworten) und Agent-Modus (Tools benutzen, max 8 Runden, Self-Check mit Confidence).
- **Forge-Workflow:** Spielidee → `/schmiede` (GDD + Tasks + Klassen) → `/geruest` (echtes `.uproject` + Source + Config) → Klassen-Batch, Assets, Git, Doku.
- **Projekte verstehen:** `/scan` findet Unreal-/Python-/Node-/C++-Projekte (nur konfigurierte Ordner), erkennt Module, Plugins, Configs, Maps, C++-Klassen, Blueprints, TODOs – mit Confidence und Risiko.
- **Autonom abarbeiten:** `/finish` (Find&Finish) löst nur sichere Tasks (Confidence ≥ 0,8, Risiko LOW/MEDIUM), mit Git-Checkpoint-Branch, Testnachweis und max 3 Versuchen pro Task. Kein Auto-Push, nie.
- **Sich erinnern:** Memory 2.0 mit Typen (Fakt, Präferenz, Entscheidung, Task, Lesson), Quellen, Projektbezug, Wichtigkeit und Ablaufdatum. Nur Relevantes landet im Prompt.
- **Sprechen & Sehen:** deutsche Stimme (neural/online, Windows/offline), Mikrofon per lokalem Whisper, Screenshots mit Vision-Modell, PC-Steuerung mit Fail-Safe.
- **Sicher stoppen:** 🔇 Stumm, 🛑 Quasseln-Stop, ⛔ Agent-Stop, ⛔ Stop-Alles (Not-Aus). Statuszeile zeigt immer den Zustand.

## Start

```powershell
.\start.ps1            # prüft Ollama + Modell, startet die App
# oder von Hand:
python quassel_ki_v20.py
```

Voraussetzungen: Python 3.12, [Ollama](https://ollama.com/download), Modelle (siehe unten).

```powershell
pip install -r requirements.txt
ollama create quassel-ki -f ollama-model\Modelfile
```

**Umzug auf den 4070-PC:** Ordner kopieren (oder Repo klonen), dann `.\setup_4070.ps1` – zieht `qwen3-coder:30b` (Fallback `qwen2.5-coder:32b`) + `moondream` und baut `quassel-ki`.

## Modelle & Hardware-Profile

Die App erkennt beim Start GPU, VRAM, RAM und installierte Modelle und wählt pro Aufgabe (FAST/BALANCED/SMART/MAXIMUM) – **zu große Modelle werden nie geladen**. Alles in `quassel.yaml` einstellbar (`/status` zeigt die Wahl).

| Profil | Beispiel | Coding-Modell | Kontext |
|---|---|---|---|
| HIGH | RTX 4070 12 GB | stark (bis ~20 GB, z.B. `qwen3-coder:30b`) | groß (16–32k) |
| MEDIUM | RTX 3060 12 GB | 7–14B quantisiert | mittel (8–16k) |
| SMALL | RTX 3060 8 GB / A1000 6 GB | 7B quantisiert | klein (4–8k) |
| CPU | ohne NVIDIA-GPU | kleines Modell | sehr klein (4k) |

Rollen: `fast` (Router, Memory, Live – z.B. `llama3.1`), `coding`, `reasoning` (z.B. `quassel-ki`), `vision` (`moondream`), `fallback`.

**Echte Messwerte** (Laptop i7-13700H + RTX A1000 6 GB, `python quassel_benchmark.py`):

| Modell | Ladezeit | Speed | Mini-Tasks |
|---|---|---|---|
| llama3.1 (8B) | ~6 s | ~4 tok/s | 3/3 |
| quassel-ki (32B) | ~16 s | ~1,5 tok/s | 3/3 |

Fazit: Auf schwacher Hardware Gerede an `fast`, 32B nur für Code/Planung. Auf der 4070 schaltet der Router automatisch hoch – dort bitte neu benchmarken.

Limit: max ~20 GB Modell-Speicher.

## Wichtigste Befehle (im Chat, `/help` zeigt alle 37)

| Befehl | Was |
|---|---|
| `/mode ask` / `/mode agent` | Nur reden / arbeiten mit Werkzeugen |
| `/speed FAST\|BALANCED\|SMART\|MAXIMUM` | Tempo vs. Gründlichkeit |
| `/stumm` `/quasseln` | Stumm / Quasseln-Stop umschalten |
| `/agentstop` `/stopalles` | Agent sauber anhalten / Not-Aus |
| `/scan [Pfad]` `/finish` | Projekte scannen / Find&Finish-Loop |
| `/schmiede Idee…` | Spielidee → GDD + tasks.json + Klassen |
| `/geruest Spielname` | Echtes `.uproject` + Source + Config |
| `/tasks` `/logcheck` `/impact Klasse` | Fortschritt, Log-Fehler + nächste Schritte, Abhängigkeiten |
| `/ton normal\|frech\|profi` | Gesprächston |
| `/verlauf` `/memory` | Gedächtnis-Zusammenfassung / Fakten zeigen |
| `/commit` `/review` `/ctx` | Git, Code-Review, Kontext |
| `/permit auto\|voll` | PC-Aktionen erlauben (Lesen = Standard) |

## Sicherheit

- **Lesen ist Standard**, Schreiben/Ausführen fragt nach (Diff-Vorschau).
- **Impact-Schutz:** HIGH/CRITICAL (Config, Projektdateien, viele Nutzer) wird in ask/auto grundsätzlich verweigert – nur Plan + Diff. Nur der Alles-Modus schreibt trotzdem (mit Warnung, deine Verantwortung).
- Stumm (🔇) = Arbeit ohne Worte; Quasseln-Stop (🛑) = nur Spontanes aus; Agent-Stop (⛔) = keine neuen Tools, Status gespeichert; STOP ALLES = Not-Aus.
- Find&Finish: nur hohe Confidence + LOW/MEDIUM, max 3 Versuche, danach dokumentierte Aufgabe + nächste. Pro Task Git-Checkpoint mit Testnachweis, nie Auto-Push.
- Blockliste für gefährliche Pfade/Befehle, alles landet in `aktionen.log`.
- Live-Maus/Tastatur nur per Button, Fail-Safe: Maus in die Ecke = Stopp.
- Stimme geht bei Teams-Calls automatisch aus (`QUASSEL_VOICE=0`).

## Architektur (kurz)

```
App (Ask/Agent/Live/Tools/Forge)
 │  Brain-Router (Schwere → Rolle → Modell, mit Kapazitätsschutz)
 │  Context-Engine (Budget 4k–32k aus Schwere + RAM)
 ├─ Memory 2.0 (typisiert, Quellen, Ablauf, Retrieval nur bei Relevanz)
 ├─ Projekt-Scanner (Index Schema v2) + Task-Discovery (Confidence/Risiko)
 ├─ Tool-System (~35 Tools, Permit + Impact-Schutz)
 └─ Agent 2.0 (Plan → Handeln → Test → Self-Check → Lesson → Doku)
```

Details: `docs/ARCHITEKTUR_AKTUELL.md`, `docs/AI_MODEL_STRATEGY.md`, `docs/MEMORY_ARCHITECTURE.md`, Entscheidungen in `docs/DECISIONS.md`, aktueller Stand in `docs/STATUS.md`.

## Speed-Tuning (`quassel.yaml`, Env `QUASSEL_*` überschreibt)

| Schlüssel | Standard | Wirkung |
|---|---|---|
| `ollama.keep_alive` | `30m` | Modell bleibt im RAM – kein Nachladen |
| `ollama.num_ctx` | `8192` | Fallback-Fenster (adaptiv regelt sonst) |
| `context.budgets` | 4k–32k | Budget je Schwere (TRIVIAL–MAX) |
| `chat.tokens` | `400` | Kürzere Antworten = schneller |
| `modelle.max_modell_gb` | auto | Niemals größere Modelle laden |
| `memory.chat_archiv_tage` | `30` | Alte Chats → `chats/archiv` (0 = aus) |
| `projekte.scan_pfade` | `[]` | Nur diese Ordner werden gescannt |

## Struktur

```
quassel_ki_v20.py      # die App (aktuell)
quassel/               # Module: hardware, modelle, memory2, konfig, projekte, schmiede, buildtest, impact, auftrag
quassel.yaml           # Konfiguration (Rollen, Speed, Memory, Agent, Projekte)
quassel_benchmark.py   # echte Messwerte (logs/benchmark_*.json)
tests/                 # Modul-Tests, headless (test_v18/v19/v20)
docs/                  # Architektur, Strategien, Roadmap, Decisions, Status
archiv/                # v1–v19 (Entwicklungsgeschichte)
ollama-model/Modelfile # Persönlichkeit + Wissen
skills/                # 10 Experten-Skills (JSON)
plugins/               # eigene Werkzeuge (Python)
start.ps1              # Ein-Klick-Start
setup_4070.ps1         # Umzug auf den 4070-PC
```

Lokal (nicht im Repo): `chats/`, `shots/`, `spiele/`, Memory-Dateien, Logs – bleibt auf deinem Rechner.

## Roadmap

- **Fertig:** v18 Foundation, v19 Project Agent, v20 (Profile, Memory, Scanner, tasks.json, Build-Adapter, Impact, Zyklen) – 76/76 Tests.
- **Nächste:** natives Tool-Calling, Skill-Lazy-Loading, 4070-Benchmarks, Memory-Konsolidierung.
- **Blockiert:** Not-Aus-E2E (manuell), UE-Build-E2E (braucht 4070-PC).

## Versionieren

```powershell
git add -A; git commit -m "was geändert wurde"
git tag v20   # bei Meilensteinen (nie pushen ohne Freigabe)
```
