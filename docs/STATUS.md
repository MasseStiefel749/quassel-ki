# Status (Lead Engineer, laufend aktualisiert)

## Phase 1 – BESTANDSAUFNAHME (02.10.2026, erledigt, BESTÄTIGT)

- Echte Version: **v19 aktiv** (`quassel_ki_v19.py`, 3143 Zeilen).
  README-Fehler gefunden: Start + Struktur nennen noch v18 → Fix in Phase 9.
- `docs/ARCHITEKTUR_AKTUELL.md` erstellt (Einstieg, Module, Speicher,
  Tools, Sicherheit, Tests).
- Memory-Duplikate gefunden: `memory.json`/`memory2.json`,
  `projekt_index.json`/`projekt_index_v19.json`; `erinnerungen.json`
  wird nie gelesen. → Phase 3/4.
- Tests Ausgangszustand: **27/27 grün** (v18: 17, v19: 10).
- Entscheidungen in `docs/DECISIONS.md` begonnen (E1–E7).

## Phase 2 – HARDWARE UND MODELLE (02.10.2026, erledigt, BESTÄTIGT)
- `hardware_klasse()` + `empfehlung()`: high/medium/small/cpu aus VRAM
  mit Abwärts-Korrektur (3060→medium, A1000→small). Echte Messung, Tabelle.
- Kapazitätsschutz im Router (`max_gb` + Ollama-Größen); Alias-Bypass per
  Test gefunden + gefixt.
- yaml: `modelle.max_modell_gb`, `context.budgets`, `chat.tokens`,
  `ollama.keep_alive/num_ctx`. Env überschreibt nur wenn gesetzt.
- Start-Banner (`_hw_banner`) dokumentiert Klasse + Modelle + Tokens.
- Kleine Modelle für Router/Memory/Live: BESTÄTIGT (`fast`-Rolle =
  llama3.1, Live nutzt llama3.1 + moondream).
- Tests: 41/41 grün (v18: 17, v19: 10, v20: 14).

## Phase 3 – WICHTIGES GEDÄCHTNIS (02.10.2026, erledigt, BESTÄTIGT)

- Einheitliches System: `memory2.json` mit Typ, Inhalt, Quelle,
  Projektbezug, Wichtigkeit 1–5, Erstellzeit, Ablaufdatum/null.
- Ablauf wird bei Abruf ignoriert + per `bereinigen()` entfernt.
- Retrieval nur bei Relevanz (Keyword + Typ + Wichtigkeit + Projekt).
- Alte Chats → `chats/archiv` (30 Tage, konfigurierbar, nie löschen).
- Episoden eingefroren (einmalig niedrig-vertraut übernommen).
- STUMM-Bypass im Stream-Finalize gefunden + gefixt (Stumm im Sprecher).
- Tests: 47/47 grün (v18: 17, v19: 10, v20: 20).
- Phase 3: Memory vereinheitlichen (Typen, Ablauf, Priorisierung).
- Phase 4: Unreal-Scanner vertiefen.
- Danach: 5 Schmiede, 6 Build/Logs, 7 Impact, 8 Agent, 9+10 Doku/Gate.
