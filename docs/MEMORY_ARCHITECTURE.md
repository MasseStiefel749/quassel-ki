# Memory-Architektur (Ziel: Memory 2.0)

## Ist (v17) → Soll

| Schicht | v17 | Memory 2.0 |
|---|---|---|
| Kurzzeit | Verlauf (10, RAM) | unverändert, + Working-Memory der Aufgabe |
| Fakten | `memory.json`: Strings, max 40 | **typisiert**: type/source/confidence/created |
| Episoden | `erinnerungen.json`: geschrieben, nie gelesen | **Feedback-Loop**: Task/Approach/Result/Lesson, Retrieval bei ähnlichen Aufgaben |
| Zusammenfassung | `zusammenfassung.json` | unverändert (funktioniert) |
| Projekt | `projekt_index.json` (Pfade) | + SAOMMO-Kontext-Chunks mit Retrieval |
| Entscheidungen | – | **Decision-Memory**: was/warum/Quelle |

## Typen (Pflichtfeld `type`)

`fact` (prüfbar) · `user_preference` · `project_fact` · `decision`
(+ `reason`) · `task` (offen/erledigt) · `lesson` (aus Fehlern) ·
`hypothesis` (unsicher, nie als Fakt ausgeben) · `unknown`

Jeder Eintrag: `{type, content, source, confidence, created}`.
Migration: alte Strings werden zu `{type: fact, source: auto-memory,
confidence: 0.6}` – nichts geht verloren, nichts wird aufgewertet.

## Retrieval-Pipeline (pro Anfrage)

```
Anfrage → Klassifizieren (fast, JSON-Schema)
  → Relevanz-Scoring je Schicht (Keyword + Typ-Boost)
  → Budget: Fakten ≤8, Episoden ≤2, Projekt-Chunks ≤3
  → Kontext bauen (Priorität: Aufgabe → Projekt → Memory → Dateien)
```

Regeln: `hypothesis`/`confidence<0.4` nur mit Unsicherheits-Marker;
`decision` wird bei verwandten Aufgaben aktiv angeboten;
veraltete Einträge (widersprochen) werden markiert, nicht gelöscht.

## Konsolidierung (nach wichtigen Sessions, schnell-Modell)

1. Neue Fakten/Entscheidungen/Fehler extrahieren (Schema, temp 0).
2. Duplikate/Widersprüche gegen Bestand prüfen.
3. Nur `confidence ≥ 0.7` oder Nutzer-bestätigt wird `fact`/`decision`;
   Rest bleibt `hypothesis`.
4. Erledigte Tasks abhaken, Lessons anlegen.

## Hallucination-Control

Antwort-Etiketten: `KNOWN` (Quelle da) · `LIKELY` · `UNCERTAIN` ·
`UNKNOWN` → dann ehrlich „weiß ich nicht" + Vorschlag, wie es
herausfindbar wäre (Tool/Doku/Web). Das Modelfile verpflichtet das
Modell darauf; der Self-Check prüft es nach (siehe Agent 2.0).
