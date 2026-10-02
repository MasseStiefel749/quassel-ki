# AI-Modell-Strategie (Hardware-adaptiv, Stand 02.10.2026)

Leitregel: **BEST_AVAILABLE_MODEL, nie fest verdrahtet.**
Auswahl = installierte Modelle × Hardware-Profil × Aufgabe.

## Hardware-Profile

| Profil | Beispiel | VRAM | RAM | Strategie |
|---|---|---|---|---|
| `laptop` | i7-13700H + RTX A1000 6 GB + 64 GB RAM (dieses Gerät) | 6 GB | 64 GB | 32B nur mit CPU-Offload (langsam); schnell = 8B; ctx 8k |
| `desktop-4070` | Ryzen 7 7700X + RTX 4070 12 GB + 32 GB RAM (Ziel-PC) | 12 GB | 32 GB | 30–32B passt großteils in VRAM; ctx 16–32k möglich |

Erkennung beim Start (`quassel/hardware.py`): nvidia-smi (GPUs, VRAM,
Treiber), RAM/CPU (Windows-API, ohne neue Dependencies), Ollama-Version,
`/api/tags` (installiert), `/api/ps` (geladen), freier Plattenplatz.

## Modell-Klassen (Rollen statt Namen)

| Rolle | Aufgabe | Laptop | 4070-Ziel |
|---|---|---|---|
| `fast` | Routing, Memory, Live-Steps, Zusammenfassung | `llama3.1` (4,9 GB) | `llama3.1` oder `qwen3:8b` |
| `coding` | Code schreiben, Debug, Forge | `quassel-ki` (32B, langsam) | `quassel-ki` auf `qwen3-coder:30b`-Basis |
| `reasoning` | Architektur, Planung, harte Nüsse | `quassel-ki` (lange Tokens) | 30B-Klasse, MAX-Modus |
| `vision` | Screenshots, Fehlersuche am Bild | `moondream` | `moondream` |
| `fallback` | Notfall, wenn stark nicht lädt | `llama3.1` | `llama3.1` |

`models.yaml` (später `quassel.yaml`) mappt Rollen → Modellnamen.
Fehlt ein Modell, rückt die Kette automatisch nach unten
(`coding → fast`), die App läuft immer.

## Auswahl-Regeln (Brain-Router)

1. **Capability-Filter:** Vision-Frage → nur Vision-Modelle; Tool-Use
   nötig → nur Modelle mit Tool-Support (Qwen2.5+/Llama3.1+).
2. **Difficulty:** TRIVIAL/LOW → `fast`; MEDIUM → `fast`, bei Code
   `coding`; HIGH/MAX → `coding`/`reasoning` (Speed-Mode beachten).
3. **Speed-Mode:** FAST zwingt `fast` (außer Vision); MAXIMUM zwingt
   stärkstes + großes Context-Budget.
4. **Kapazität:** passt das Modell nicht in (VRAM + RAM-Puffer), nimm
   das größte passende. Faustformel: Q4-Modell braucht ≈ 1,1 ×
   Blob-Größe an Speicher zum Laden.

## Benchmark-Politik (keine Fake-Werte)

- `quassel_benchmark.py` misst **echt**: Ladezeit, Prompt-Eval, tok/s,
  Erfolg/Fehlschlag – pro installiertem Modell, mit Timeout.
- Qualitäts-Urteile (Coding/Reasoning) kommen aus **realen Mini-Tasks**
  (vom Modell gelöst + per Skript geprüft: bestanden/nicht bestanden),
  nicht aus erfundenen Scores.
- Ergebnisse landen in `logs/benchmark_<datum>.json` und füttern die
  Modellwahl (schnellstes bestandenes Modell pro Rolle).

## 4070-Plan (wenn der PC da ist)

1. `setup_4070.ps1` zieht `qwen3-coder:30b` (Fallback `qwen2.5-coder:32b`)
   + `moondream`, baut `quassel-ki` auf der 30B-Basis.
2. `quassel-benchmark` laufen lassen → echte tok/s auf 4070 messen.
3. `ctx` auf 16–32k heben (nur wenn Benchmark stabil).
4. Optional prüfen (2026er Modelle, nur wenn 20-GB-Limit hält):
   kompakte Coding-Modelle als `fast`-Ersatz mit mehr Verstand.

## Speicher-Limit

Max ~20 GB Modell-Blobs (C:-Platte, Stand 02.10.2026: 24 GB frei).
`quassel-ki` teilt sich Layer mit `qwen2.5-coder:32b` (gleiche Basis) –
`ollama list` zeigt nominal 19+19 GB, real weniger. Aufräumen:
`ManishThota/llava_next_video` (4,7 GB, ungenutzt) ist Lösch-Kandidat
(`ollama rm`), sobald moondream als Vision bestätigt ist.
