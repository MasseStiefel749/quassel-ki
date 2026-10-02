# ❯ Quassel-KI

Lokaler **AI Game Development Assistant** für Unreal Engine (UE 5.8) – läuft komplett offline auf dem eigenen PC, kein Cloud-Abo, keine Daten gehen raus.

**Stand: v20** – Autonomous Project Agent mit Brain-Router, Hardware-Profilen, Memory 2.0, Unreal-Scanner, tasks.json, Build/Test-Adapter, Impact-Schutz, Find&Finish. Details: `docs/`.

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

Die App erkennt beim Start GPU, VRAM, RAM und installierte Modelle und
wählt pro Aufgabe (FAST/BALANCED/SMART/MAXIMUM) – zu große Modelle werden
nie geladen. Alles in `quassel.yaml` einstellbar (`/status` zeigt die Wahl).

| Profil | Beispiel | Coding-Modell | Kontext |
|---|---|---|---|
| HIGH | RTX 4070 12 GB | stark (bis ~20 GB, z.B. `qwen3-coder:30b`) | groß (16–32k) |
| MEDIUM | RTX 3060 12 GB | 7–14B quantisiert | mittel (8–16k) |
| SMALL | RTX 3060 8 GB / A1000 6 GB | 7B quantisiert | klein (4–8k) |
| CPU | ohne NVIDIA-GPU | kleines Modell | sehr klein (4k) |

Rollen: `fast` (Router, Memory, Live), `coding`, `reasoning`, `vision`
(`moondream`), `fallback`. Echte Messwerte: `python quassel_benchmark.py`.

Limit: max ~20 GB Modell-Speicher.

## Wichtigste Befehle (im Chat)

| Befehl | Was |
|---|---|
| `/mode ask` / `/mode agent` | Nur reden / arbeiten mit Werkzeugen |
| `/speed FAST\|BALANCED\|SMART\|MAXIMUM` | Tempo vs. Gründlichkeit (v18) |
| `/stumm` `/quasseln` | Stumm / Quasseln-Stop umschalten (v19) |
| `/scan [Pfad]` `/finish` | Projekte scannen / Find&Finish-Loop (v19) |
| `/agentstop` `/stopalles` | Agent sauber anhalten / Not-Aus (v19) |
| `/schmiede Idee…` | Spielidee → GDD.md + tasks.md + klassen.md |
| `/geruest Spielname` | Echtes `.uproject` + Source + Config |
| `/tasks` `/logcheck` `/impact Klasse` | Fortschritt, Log-Fehler, Abhängigkeiten |
| `/ton normal\|frech\|profi` | Gesprächston |
| `/verlauf` | Gedächtnis-Zusammenfassung zeigen |
| `/commit` `/review` `/memory` `/ctx` | Git, Code-Review, Fakten, Kontext |
| `/permit auto\|voll` | PC-Aktionen erlauben (Lesen = Standard) |

## Sicherheit

- **Lesen ist Standard**, Schreiben/Ausführen fragt nach (Diff-Vorschau).
- **Impact-Schutz:** HIGH/CRITICAL (Config, Projektdateien, viele Nutzer)
  wird in ask/auto grundsätzlich verweigert – nur Plan + Diff. Nur der
  Alles-Modus schreibt trotzdem (mit Warnung, deine Verantwortung).
- Stumm (🔇) = Arbeit ohne Worte; Quasseln-Stop (🛑) = nur Spontanes aus;
  Agent-Stop (⛔) = keine neuen Tools, Status gespeichert; STOP ALLES = Not-Aus.
- Find&Finish bearbeitet NUR Tasks mit hoher Confidence + Risiko LOW/MEDIUM,
  max 3 Versuche pro Task, danach dokumentierte Aufgabe + nächste.
  Pro Task ein Git-Checkpoint-Branch mit Testnachweis, nie Auto-Push.
- Blockliste für gefährliche Pfade/Befehle, alles landet in `aktionen.log`.
- Live-Maus/Tastatur nur per Button, Fail-Safe: Maus in die Ecke = Stopp.
- Stimme geht bei Teams-Calls automatisch aus (`QUASSEL_VOICE=0`).

## Speed-Tuning (`quassel.yaml`, Env `QUASSEL_*` überschreibt)

| Schlüssel | Standard | Wirkung |
|---|---|---|
| `ollama.keep_alive` | `30m` | Modell bleibt im RAM – kein Nachladen |
| `ollama.num_ctx` | `8192` | Fallback-Fenster (adaptiv regelt sonst) |
| `context.budgets` | 4k–32k | Budget je Schwere (TRIVIAL–MAX) |
| `chat.tokens` | `400` | Kürzere Antworten = schneller |
| `modelle.max_modell_gb` | auto | Niemals größere Modelle laden |

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
memory.json / zusammenfassung.json / erinnerungen.json  # Gedächtnis
chats/ shots/ spiele/  # Sessions, Screenshots, Forge-Projekte
```

## Versionieren

```powershell
git add -A; git commit -m "was geändert wurde"
git tag v20   # bei Meilensteinen (nie pushen ohne Freigabe)
```
