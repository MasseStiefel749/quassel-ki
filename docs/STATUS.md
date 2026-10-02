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

## Phasen 4–8 (02.10.2026, erledigt, BESTÄTIGT)

- P4: Unreal-Details (Module, Plugins, Configs, Maps, UCLASS/STRUCT/ENUM,
  Blueprint-Pfade ehrlich ohne Inhalt), Index-Schema v2, Fixture-Tests.
- P5: tasks.json (ID, Ziel, Akzeptanz, Dateien/Systeme, Abhängigkeiten,
  Risiko, Testschritte, Status, Kategorie, Annahmen), Validierung,
  Auto-Split, Markdown-Import, MCP-Tools, E2E BESTÄTIGT.
- P6: Build/Test-Adapter (echte Läufe, Zeitstempel-Logs, Ursachen-Heuristik,
  nächste Schritte), `/logcheck` liefert Schritte, Permit-Gate für Läufe.
- P7: Impact (Referenzen, Module, Tests, Byte-Suche in Assets, Risiko),
  Schreibschutz HIGH/CRITICAL vor Permit.
- P8: Zyklen (Impact-Gate, 3 Strikes + dokumentierte Aufgabe, Testnachweis,
  Doku pro Task, Rollback-Funktion). Not-Aus-E2E bleibt manueller Test
  (braucht laufende App + Klick) → siehe Offene Risiken.
- Tests: 76/76 grün (v18: 17, v19: 16, v20: 43).

## Phasen 9+10 – DOKU + GATE (02.10.2026, erledigt, BESTÄTIGT)

- README: v20, Profile (4070/3060/CPU), Sicherheitsmodell, Befehle, yaml-Tuning.
- ROADMAP: erledigt/nächste/blockiert. `/help` vollständig (alle Stops + Scan/Finish).
- Umbenannt: `quassel_ki_v20.py`, v17–v19 im Archiv, Skripte zeigen auf v20.
- Qualitätsgate: 76/76 Tests grün, Compile ok, Import+Config ok,
  Secret-Scan 0 Treffer, keine Modell-Blobs, keine Zugangsdaten.
  Laufzeit-Daten enttrackt (E19). NICHT gepusht (E20).
- Offene Risiken: Not-Aus-E2E manuell; UE-Build-E2E erst auf 4070-PC;
  4070-Werte erst nach Umzug; llava-Modell (4,7 GB) ungenutzt.
- Manuelle Voraussetzungen: `pip install -r requirements.txt`, Ollama +
  `ollama create quassel-ki -f ollama-model/Modelfile`, Start per `start.ps1`.
- Nächster sinnvoller Schritt: v20 starten + Rauchtest im Chat
  (`/status`, `/scan`, `/memory`), danach nativen Tool-Calling angehen.
- Phase 3: Memory vereinheitlichen (Typen, Ablauf, Priorisierung).
- Phase 4: Unreal-Scanner vertiefen.
- Danach: 5 Schmiede, 6 Build/Logs, 7 Impact, 8 Agent, 9+10 Doku/Gate.
