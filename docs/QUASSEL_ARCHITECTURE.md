# QUASSEL-KI – Architektur (Stand v17, 02.10.2026)

## CURRENT ARCHITECTURE

```
quassel_ki_v17.py (2700 Zeilen, Single-File-App, Tkinter)
│
├─ Ask-Modus: Streaming-Chat (ollama_stream, QUASSEL_CHAT_TOKENS=400)
├─ Agent-Modus: Tool-Loop, max 8 Runden, Permit-Stufen, Self-Healing (.py)
├─ Live-Tab: Screenshot → moondream → Klick/Tippe-Sequenzen (pyautogui)
├─ Tools-Tab: Forge-Buttons, Skills, Plugins, UE-Doku, Git
├─ MCP: lokal/datei+git+forge+unreal | Beispiel-Filesystem-Server (deaktiviert)
├─ Voice: Edge-TTS (online) → pyttsx3 (offline), Whisper-Mikro (base, CPU/int8)
└─ Skills (10, JSON, Trigger-Scoring) + Plugins (Python-Module, Hot-Reload)
```

**Kontext-Pipeline (Ask):** Memory-Fakten → Ton → Rolling-Summary →
Chat-Recall (alte Chats, Keyword-Scoring) → quassel.md-Regeln → Skill →
Anhänge → Verlauf (letzte 10). Danach Router (schnell/stark, llama3.1).

**Modell-Aufrufe:** alle über `/api/chat` (urllib, kein SDK):
`ollama_stream` (Chat), `ollama_chat_once` (Agent/Reviews),
`ollama_json` (Schema + temperature 0, für Auto-Memory).
`keep_alive=30m`, `num_ctx=8192` (env-überschreibbar).

## CURRENT MODELS

| Rolle | Modell | Größe | Wofür |
|---|---|---|---|
| stark | `quassel-ki` (qwen2.5-coder:32b-Basis + Modelfile) | ~19 GB | Chat, Agent, Schmiede |
| schnell | `llama3.1` | ~4,9 GB | Router, Memory, Live |
| vision | `moondream` | ~1,7 GB | Screenshots |
| ungenutzt | `ManishThota/llava_next_video` | ~4,7 GB | – (Kandidat zum Löschen) |

Fest verdrahtet: `OLLAMA_MODEL` (env `QUASSEL_MODEL`), `AGENT_MODEL`,
`FAST_MODEL`, `VISION_MODEL`. Router-Entscheidung nur schnell/stark per
Heuristik (Länge, Codewörter, UE-Begriffe). **Kein Hardware-Wissen.**

## CURRENT MEMORY

| Schicht | Datei | Stand |
|---|---|---|
| Fakten (max 40, Strings) | `memory.json` | **leer** – Auto-Memory lief kaum |
| Rolling Summary | `zusammenfassung.json` | vorhanden, getestet |
| Episoden (max 120) | `erinnerungen.json` | geschrieben, nie gelesen! |
| Chat-Recall | `chats/*.json` + Keyword-Scoring | funktioniert (getestet) |
| Projektindex | `projekt_index.json` | vorhanden |

**Lücken:** keine Typen/Quellen/Confidence, kein Retrieval-Ranking über
Schichten, keine Konsolidierung (Dedup nur exakte Strings), Episoden
werden gespeichert aber nie wieder abgerufen.

## CURRENT TOOLS

~35 lokale Tools in `MCPClient.aufrufen` (Datei, Git, UE-Doku, Forge:
Gerüst/Batch/Assets/Tasks/Checks/Impact/Log). Keine Metadaten
(Name/Doku-String im Code, kein Risiko-Flag, keine Kategorie).
Permit: lesen/auto/voll + Blockliste + Diff-Vorschau + `aktionen.log`.
Bekannte Bugs (gefixt in v15–v17): Git-`ordner`-Klammer, cpp_check-Header,
Agent-`verlauf`-UnboundLocalError, quassel.md-Typo.

## CURRENT PROBLEMS

1. **Modelle fest verdrahtet** – kein Hardware-Check, kein Fallback,
   kein Benchmark, keine Austauschbarkeit ohne Code-Edit.
2. **Kontext starr** – `num_ctx=8192` fix, Verlauf 10 fix (env), keine
   Budget-Rechnung aus Modell/RAM/Aufgabe.
3. **Memory flach** – untypisiert, ohne Quellen, ohne Konsolidierung,
   Episoden ungenutzt.
4. **Agent ohne Verifikation** – kein Self-Check, kein Lesson-Loop.
5. **Keine Observability** – Antwortzeit steht im Status, sonst keine
   Metriken (tok/s, VRAM, Fehlerquoten).
6. **Konfig im Code** – ~15 `os.environ`-Reads verstreut, keine Datei.
7. **App-Prozess tot** – v17 (PID 24216) läuft nicht mehr; kein
   Autostart/Watchdog.

## BIGGEST BOTTLENECKS

1. **32B-Modell auf 6-GB-VRAM-Laptop** – erste Antwort nach Idle 60 s+
   (trotz keep_alive, da Ollama bei RAM-Druck entlädt). → Rollen-Trennung
   + Speed-Modes + kleinere Coding-Modelle als Option.
2. **Ein 2700-Zeilen-File** – jede Änderung riskiert Seiteneffekte.
   → Neue Systeme als Module in `quassel/`, App bleibt Hülle.
3. **Kein echtes Tool-Calling** – JSON-Blöcke parsen ist fragil.
   (Qwen2.5 unterstützt natives Tool-Calling – später migrieren.)

## PROPOSED ARCHITECTURE (v18+)

```
                    QUASSEL-APP (UI, Modi, Sicherheit)
                               │
                    ┌──────────┴──────────┐
              BRAIN-ROUTER          RESOURCE-MGR
        (Difficulty→Rolle→Modell)   (Load/Unload/Queue)
                    │                       │
              CONTEXT-ENGINE (Budget aus Modell+RAM+Aufgabe)
                    │
        ┌───────────┼───────────┐
     MEMORY 2.0   PROJEKT      SKILLS
   (typisiert,    (Index +     (modular,
    Retrieval)     Recall)      lazy)
                    │
               TOOL-SYSTEM (Metadaten, Kategorien, Risiko)
                    │
              AGENT 2.0 (Plan→Act→Test→Verify→Lesson)
                    │
               SELF-CHECK + FEEDBACK-LOOP
```

Prinzipien: **nichts Hartes** (Modelle, Pfade, Budgets aus
`quassel.yaml` + Hardware-Profil), **nichts Fake** (jede Anzeige hat
eine echte Messung/Funktion dahinter), **kleine Commits**.

## IMPLEMENTATION ORDER

1. v18 Foundation: `quassel/`-Paket (hardware, modelselect, memory2,
   konfig), Router-Rollen, Speed-Modes, Context-Budget, Agent-Self-Check,
   Feedback-Loop, Benchmark-Skript (echte Messwerte), Tests, Docs.
2. v19 Adaptive Brain: natives Tool-Calling (Qwen), Skill-Lazy-Loading,
   Multi-GPU-Erkennung, 4070-Profil.
3. v20 Memory 2.0 voll: Konsolidierungs-Job, Episoden-Retrieval,
   Decision-Memory, Confidence-Anzeige.
4. Danach: Agent 2.0 (Plan-Docs), Research-Skill, Business-Skill.
