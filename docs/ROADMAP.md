# Roadmap: Quassel wird erwachsen

Jede Version braucht messbare Verbesserung + Test. Kein Fake.

## v18 Foundation (diese Runde)

- [ ] `quassel/`-Paket: hardware, modelle (Rollen+Auswahl), memory2, konfig
- [ ] `quassel.yaml`: alle Einstellungen aus dem Code gezogen
- [ ] Hardware-Profil beim Start (`/status` zeigt GPU/VRAM/RAM/Modelle)
- [ ] Brain-Router: Difficulty (TRIVIAL–MAX) → Rolle → Modell, Speed-Modes
- [ ] Context-Budget `context_budget()` statt fix 8192
- [ ] Memory 2.0 Basis: Typen/Quellen/Confidence + Migration
- [ ] Agent Self-Check nach komplexen Aufgaben + Feedback-Loop (Lessons)
- [ ] `quassel_benchmark.py`: echte Messwerte (Ladezeit, tok/s, Mini-Tasks)
- [ ] `tests/`: Modul-Tests, headless lauffähig
- [ ] Messbar: `/status` zeigt echte Hardware; Router-Entscheidung im Log;
      Lessons werden bei Wiederholungsaufgaben abgerufen

## v19 Adaptive Brain

- Natives Ollama-Tool-Calling (Qwen2.5+) statt JSON-Block-Parsing
- Skill-Lazy-Loading (nur benötigte Skills in den Prompt)
- Multi-GPU-Erkennung, 4070-Profil mit echten Benchmarks
- Messbar: Tool-Fehlerrate sinkt, Prompt schrumpft

## v20 Memory voll

- Konsolidierungs-Job, Episoden-Retrieval, Decision-Memory-UI
- Confidence-Anzeige im `/memory`
- Messbar: Wiederholungsfragen ohne erneutes Erklären

## v21+ (später)

- Agent 2.0 (Plan-Dokumente), Research-Skill, Business-Skill
- Autonome Entwicklungsaufgaben mit Verifikation
