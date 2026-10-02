# Entscheidungen (Lead Engineer Log)

Jede sichere Standardentscheidung wird hier festgehalten statt nachzufragen.

## 2026-10-02 – Phase 1

- **E1: Kein Push ohne Freigabe.** Regel aus dem Auftrag, gilt dauerhaft.
  Checkpoints = lokale Commits/Branches.
- **E2: Größere Änderungen auf Feature-Branches** (`feat/...`), Docs und
  kleine Fixes direkt auf `main`.
- **E3: `memory.json` vorerst nicht löschen.** Noch 0 Einträge, aber
  Auto-Memory schreibt parallel in beide Systeme. Vereinheitlichung kommt
  in Phase 3 (Migration + Abschalten der Doppelschreibweise).
- **E4: `projekt_index.json` (alt) bleibt bis Phase 4 liegen.** Wird nur
  noch von `/index` gelesen; v19-Index ist getrennt. Entfernung nach
  Migration des Befehls.
- **E5: `erinnerungen.json` wird in Phase 3 als Episoden-Quelle angebunden**
  statt gelöscht – Inhalt ist neu, Verlust wäre unnötig.
- **E6: Kein neues pip-Paket ohne Not.** pyyaml ist drin (für quassel.yaml),
  Rest mit Standardbibliothek.
- **E7: Benchmark misst nur, was Ollama hergibt** (load_duration,
  eval_count/duration) + Mini-Tasks mit Skript-Prüfung. Keine erfundenen
  Quality-Scores.

## 2026-10-02 – Phase 2

- **E8: Hardware-Klassen nach VRAM, mit Abwärts-Korrektur für bekannte
  Karten.** Eine RTX 3060 12 GB KANN 30B-Modelle laden, ist dabei aber so
  langsam, dass 7–14B praktisch mehr bringen. Korrektur wirkt nur abwärts,
  nie aufwärts. Klasse steuert `max_modell_gb`, Context und Keep-Alive.
- **E9: Kapazitätsschutz im Router, nicht nur Doku.** `waehle_modell`
  filtert per Ollama-Größen (`/api/tags`), unbekannte Größen blockieren
  nicht (Ollama meldet echten Fehler). Ein Test hat einen Alias-Bypass
  gefunden und gefixt (BESTÄTIGT durch Test).
- **E10: yaml gewinnt, Env überschreibt.** `quassel.yaml` (ollama, chat,
  context.budgets, modelle.max_modell_gb) ist Standard; `QUASSEL_*`-Env
  nur bei Bedarf. Kein doppeltes Lesen mehr.
- **E11: Dateiname bleibt `quassel_ki_v19.py` bis zum Phasenende.**
  Umbenennen auf v20 erst, wenn alle Phasen drin sind (weniger
  Verwechslungsrisiko während der Arbeit).
