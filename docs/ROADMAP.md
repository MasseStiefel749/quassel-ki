# Roadmap: Quassel wird erwachsen (Stand 02.10.2026, v20)

Jede Version braucht messbare Verbesserungen + Tests. Kein Fake.

## Erledigt (BESTÄTIGT durch Tests)

- **v18 Foundation:** `quassel/`-Paket, Brain-Router, Speed-Modes,
  Context-Budget, Memory 2.0 Basis, Agent Self-Check, Benchmark.
- **v19 Autonomous Project Agent:** Stumm/Stops, Projekt-Scanner,
  Task-Discovery, Find&Finish mit Git-Checkpoints.
- **v20 (dieser Branch):** Hardware-Profile (high/medium/small/cpu) +
  Kapazitätsschutz, Memory vereint (Typen, Ablauf, Archiv), Unreal-Details
  (Schema v2), tasks.json, Build/Test-Adapter, Impact + Schreibschutz,
  Agent-Zyklen (3 Strikes, Testnachweis, Rollback).
- Tests: 76/76 grün. Benchmarks: echte Messwerte in `logs/`.

## Als Nächstes

- Natives Ollama-Tool-Calling (statt JSON-Block-Parsing) – weniger Fragilität.
- Skill-Lazy-Loading (nur benötigte Skills in den Prompt).
- 4070-Profil mit echten Benchmarks (braucht den 4070-PC).
- Konsolidierungs-Job für Memory (Duplikate, Widersprüche).
- `ManishThota/llava_next_video` (4,7 GB) löschen, wenn moondream reicht.

## Blockiert (braucht Nutzer/Hardware)

- **Not-Aus-E2E:** braucht laufende App + echten Klick – manuell testen.
- **UE-Build-E2E:** kein Unreal auf diesem Laptop – erst auf 4070-PC möglich.
- **Echte 4070-Werte:** erst nach Umzug messbar.
- **Public-Repo-Hygiene:** Chats/Shots/Logs laufen mit (Nutzer wollte public);
  `.gitignore`-Verschärfung ausstehend (siehe Qualitätsgate).
