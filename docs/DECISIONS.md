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
