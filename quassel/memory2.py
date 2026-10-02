# -*- coding: utf-8 -*-
"""Memory 2.0: typisierte Erinnerungen mit Quelle + Confidence. Migriert memory.json verlustfrei."""
from __future__ import annotations
import json
import re
import time
from datetime import datetime
from pathlib import Path

TYPEN = ("fact", "user_preference", "project_fact", "decision",
         "task", "lesson", "hypothesis", "unknown")

_STOPW = {"der", "die", "das", "und", "oder", "ist", "war", "ich", "du", "er", "sie",
          "es", "mit", "von", "für", "auf", "in", "zu", "dem", "den", "ein", "eine",
          "nicht", "aber", "wie", "was", "mach", "kann", "noch", "wir", "mir", "mich",
          "dich", "uns", "hat", "haben", "sind", "wird", "man", "auch", "sich", "bei"}


def _begriffe(text):
    return {w for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9_]{4,}", str(text).lower()) if w not in _STOPW}


def _norm_inhalt(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def neu(typ, inhalt, quelle="manuell", vertrauen=0.7):
    if typ not in TYPEN:
        typ = "unknown"
    try: vertrauen = max(0.0, min(1.0, float(vertrauen)))
    except Exception: vertrauen = 0.5
    return {"type": typ, "content": str(inhalt).strip()[:400], "source": str(quelle)[:120],
            "confidence": round(vertrauen, 2),
            "created": datetime.now().isoformat(timespec="seconds")}


def laden(pfad):
    try:
        p = Path(str(pfad))
        if p.exists():
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and isinstance(obj.get("eintraege"), list):
                return obj
    except Exception:
        pass
    return {"eintraege": []}


def speichern(pfad, daten):
    Path(str(pfad)).write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")


def migrieren(alt_pfad, neu_pfad):
    """memory.json (Strings) -> memory2.json (typisiert). Nichts geht verloren, nichts wird aufgewertet."""
    alt_fakten = []
    try:
        p = Path(str(alt_pfad))
        if p.exists():
            alt_fakten = json.loads(p.read_text(encoding="utf-8")).get("fakten", [])
    except Exception:
        pass
    daten = laden(neu_pfad)
    bekannt = {_norm_inhalt(e.get("content", "")) for e in daten["eintraege"]}
    zugelegt = 0
    for f in alt_fakten:
        if _norm_inhalt(f) and _norm_inhalt(f) not in bekannt:
            daten["eintraege"].append(neu("fact", f, quelle="auto-memory (migriert)", vertrauen=0.6))
            bekannt.add(_norm_inhalt(f))
            zugelegt += 1
    daten["eintraege"] = daten["eintraege"][-300:]
    speichern(neu_pfad, daten)
    return zugelegt


def hinzufuegen(pfad, typ, inhalt, quelle="manuell", vertrauen=0.7):
    daten = laden(pfad)
    norm = _norm_inhalt(inhalt)
    if not norm:
        return daten
    for e in daten["eintraege"]:
        if _norm_inhalt(e.get("content", "")) == norm:
            e["confidence"] = max(e.get("confidence", 0), round(max(0.0, min(1.0, float(vertrauen))), 2))
            if quelle and quelle not in e.get("source", ""):
                e["source"] = (e.get("source", "") + " + " + quelle)[:120]
            speichern(pfad, daten)
            return daten
    daten["eintraege"].append(neu(typ, inhalt, quelle, vertrauen))
    daten["eintraege"] = daten["eintraege"][-300:]
    speichern(pfad, daten)
    return daten


def abrufen(pfad, frage, limit_fakten=8, limit_episoden=2):
    """Relevanz-Scoring: Keyword-Schnitt + Typ-Boost. Unsicheres nur markiert."""
    daten = laden(pfad)
    q = _begriffe(frage)
    if not q:
        return []
    boost = {"decision": 3, "lesson": 3, "project_fact": 2, "task": 2,
             "fact": 1, "user_preference": 1, "hypothesis": 0, "unknown": 0}
    treffer = []
    for e in daten["eintraege"]:
        w = _begriffe(e.get("content", ""))
        punkte = len(q & w) + boost.get(e.get("type"), 0) * (1 if (q & w) else 0)
        if e.get("type") == "decision" and (q & w):
            punkte += 2
        if punkte > 0:
            treffer.append((punkte, e))
    treffer.sort(key=lambda x: -x[0])
    fakten = [e for _, e in treffer if e.get("type") != "lesson"][:limit_fakten]
    episoden = [e for _, e in treffer if e.get("type") == "lesson"][:limit_episoden]
    return fakten + episoden


def als_systemtext(eintraege):
    zeilen = []
    for e in eintraege:
        c = e.get("confidence", 0)
        mark = "" if c >= 0.7 else (" (unsicher)" if c >= 0.4 else " (Vermutung!)")
        zeilen.append(f"- [{e.get('type')}] {e.get('content')}{mark}")
    return "\n".join(zeilen)


def veraltet_markieren(pfad, inhalt):
    daten = laden(pfad)
    norm = _norm_inhalt(inhalt)
    for e in daten["eintraege"]:
        if _norm_inhalt(e.get("content", "")) == norm:
            e["type"] = "hypothesis"
            e["confidence"] = 0.2
            e["source"] = (e.get("source", "") + " [widersprochen]")[:120]
    speichern(pfad, daten)
    return daten
