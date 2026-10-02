# ❯ Quassel-KI

Lokaler **AI Game Development Assistant** für Unreal Engine (UE 5.8) – läuft komplett offline auf dem eigenen PC, kein Cloud-Abo, keine Daten gehen raus.

**Stand: v18 Foundation** – Brain-Router (Difficulty → Rolle → Modell), Hardware-Profil beim Start, Speed-Modes, adaptives Context-Budget, Memory 2.0 (Typen/Quellen/Confidence), Agent Self-Check + Lesson-Loop, `quassel.yaml`-Konfig, echter Benchmark. Details: `docs/`.

## Start

```powershell
.\start.ps1            # prüft Ollama + Modell, startet die App
# oder von Hand:
python quassel_ki_v18.py
```

Voraussetzungen: Python 3.12, [Ollama](https://ollama.com/download), Modelle (siehe unten).

```powershell
pip install -r requirements.txt
ollama create quassel-ki -f ollama-model\Modelfile
```

**Umzug auf den 4070-PC:** Ordner kopieren (oder Repo klonen), dann `.\setup_4070.ps1` – zieht `qwen3-coder:30b` (Fallback `qwen2.5-coder:32b`) + `moondream` und baut `quassel-ki`.

## Modelle

| Zweck | Modell | Größe |
|---|---|---|
| Stark (Coden, Schmiede) | `quassel-ki` (Basis `qwen2.5-coder:32b`) | ~19 GB |
| Schnell (Router, Memory, Live) | `llama3.1` | ~5 GB |
| Augen (Screenshots) | `moondream` | ~1,7 GB |

Limit: max ~20 GB Modell-Speicher.

## Wichtigste Befehle (im Chat)

| Befehl | Was |
|---|---|
| `/mode ask` / `/mode agent` | Nur reden / arbeiten mit Werkzeugen |
| `/speed FAST\|BALANCED\|SMART\|MAXIMUM` | Tempo vs. Gründlichkeit (v18) |
| `/schmiede Idee…` | Spielidee → GDD.md + tasks.md + klassen.md |
| `/geruest Spielname` | Echtes `.uproject` + Source + Config |
| `/tasks` `/logcheck` `/impact Klasse` | Fortschritt, Log-Fehler, Abhängigkeiten |
| `/ton normal\|frech\|profi` | Gesprächston |
| `/verlauf` | Gedächtnis-Zusammenfassung zeigen |
| `/commit` `/review` `/memory` `/ctx` | Git, Code-Review, Fakten, Kontext |
| `/permit auto\|voll` | PC-Aktionen erlauben (Lesen = Standard) |

## Sicherheit

- **Lesen ist Standard**, Schreiben/Ausführen fragt nach (Diff-Vorschau).
- Blockliste für gefährliche Pfade/Befehle, alles landet in `aktionen.log`.
- Live-Maus/Tastatur nur per Button, Fail-Safe: Maus in die Ecke = Stopp.
- Stimme geht bei Teams-Calls automatisch aus (`QUASSEL_VOICE=0`).

## Speed-Tuning (Umgebungsvariablen)

| Variable | Standard | Wirkung |
|---|---|---|
| `QUASSEL_KEEP_ALIVE` | `30m` | Modell bleibt im RAM – kein Nachladen |
| `QUASSEL_NUM_CTX` | `8192` | Kontextfenster |
| `QUASSEL_CHAT_TOKENS` | `400` | Kürzere Antworten = schneller |
| `QUASSEL_NUM_GPU` | `0` (= auto) | GPU-Schichten erzwingen |

## Struktur

```
quassel_ki_v18.py      # die App (aktuell)
quassel/               # v18-Module: hardware, modelle, memory2, konfig
quassel.yaml           # Konfiguration (Rollen, Speed, Memory, Agent)
quassel_benchmark.py   # echte Messwerte (logs/benchmark_*.json)
tests/test_v18.py      # 17 Modul-Tests (headless)
docs/                  # Architektur, Modell-Strategie, Memory, Roadmap
archiv/                # v1–v17 (Entwicklungsgeschichte)
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
git tag v18   # bei Meilensteinen
```
