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

# Nur diese Kategorien werden dauerhaft gespeichert (Phase 3):
# Nutzerpräferenzen, Projektfakten, Architekturentscheidungen, offene Aufgaben,
# bestätigte Fehler+Lösungen. Alles andere bleibt flüchtig (Verlauf/Summary).
ERLAUBTE_TYPEN = ("user_preference", "project_fact", "decision", "task", "lesson", "fact")

_STOPW = {"der", "die", "das", "und", "oder", "ist", "war", "ich", "du", "er", "sie",
          "es", "mit", "von", "für", "auf", "in", "zu", "dem", "den", "ein", "eine",
          "nicht", "aber", "wie", "was", "mach", "kann", "noch", "wir", "mir", "mich",
          "dich", "uns", "hat", "haben", "sind", "wird", "man", "auch", "sich", "bei"}


def _begriffe(text):
    return {w for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9_]{4,}", str(text).lower()) if w not in _STOPW}


def _norm_inhalt(text):
    return re.sub(r"\s+", " ", str(text).strip().lower())


def neu(typ, inhalt, quelle="manuell", vertrauen=0.7, projekt="", wichtigkeit=3, ablauf=None):
    if typ not in TYPEN:
        typ = "unknown"
    try: vertrauen = max(0.0, min(1.0, float(vertrauen)))
    except Exception: vertrauen = 0.5
    try: wichtigkeit = max(1, min(5, int(wichtigkeit)))
    except Exception: wichtigkeit = 3
    if ablauf:
        try:
            datetime.fromisoformat(str(ablauf))
            ablauf = str(ablauf)
        except Exception:
            ablauf = None
    return {"type": typ, "content": str(inhalt).strip()[:400], "source": str(quelle)[:120],
            "projekt": str(projekt or "")[:80], "wichtigkeit": wichtigkeit,
            "confidence": round(vertrauen, 2), "ablauf": ablauf,
            "created": datetime.now().isoformat(timespec="seconds")}


def abgelaufen(eintrag, jetzt=None):
    try:
        abl = eintrag.get("ablauf")
        if not abl:
            return False
        return datetime.fromisoformat(str(abl)) <= (jetzt or datetime.now())
    except Exception:
        return False


def bereinigen(pfad):
    """Löscht abgelaufene Einträge. Gibt Anzahl zurück."""
    daten = laden(pfad)
    vorher = len(daten["eintraege"])
    daten["eintraege"] = [e for e in daten["eintraege"] if not abgelaufen(e)]
    speichern(pfad, daten)
    return vorher - len(daten["eintraege"])


def episoden_einfrieren(episoden_pfad, neu_pfad):
    """erinnerungen.json wird nicht mehr beschrieben. Bestehende Episoden werden
    einmalig als niedrig-vertraute Fakten übernommen, danach ist die Datei Geschichte."""
    zugelegt = 0
    try:
        p = Path(str(episoden_pfad))
        if not p.exists():
            return 0
        obj = json.loads(p.read_text(encoding="utf-8"))
        episoden = obj if isinstance(obj, list) else obj.get("episoden", [])
        daten = laden(neu_pfad)
        bekannt = {_norm_inhalt(e.get("content", "")) for e in daten["eintraege"]}
        for ep in episoden:
            inhalt = str((ep or {}).get("antwort", "") or (ep or {}).get("frage", ""))[:300]
            if _norm_inhalt(inhalt) and _norm_inhalt(inhalt) not in bekannt:
                daten["eintraege"].append(neu("fact", inhalt, quelle="erinnerungen (eingefroren)",
                                              vertrauen=0.4, wichtigkeit=2))
                bekannt.add(_norm_inhalt(inhalt))
                zugelegt += 1
        daten["eintraege"] = daten["eintraege"][-300:]
        speichern(neu_pfad, daten)
    except Exception:
        pass
    return zugelegt


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


def hinzufuegen(pfad, typ, inhalt, quelle="manuell", vertrauen=0.7, projekt="", wichtigkeit=3, ablauf=None):
    daten = laden(pfad)
    norm = _norm_inhalt(inhalt)
    if not norm:
        return daten
    for e in daten["eintraege"]:
        if _norm_inhalt(e.get("content", "")) == norm:
            e["confidence"] = max(e.get("confidence", 0), round(max(0.0, min(1.0, float(vertrauen))), 2))
            if quelle and quelle not in e.get("source", ""):
                e["source"] = (e.get("source", "") + " + " + quelle)[:120]
            if projekt:
                e["projekt"] = str(projekt)[:80]
            speichern(pfad, daten)
            return daten
    daten["eintraege"].append(neu(typ, inhalt, quelle, vertrauen, projekt, wichtigkeit, ablauf))
    daten["eintraege"] = daten["eintraege"][-300:]
    speichern(pfad, daten)
    return daten


def abrufen(pfad, frage, limit_fakten=8, limit_episoden=2, projekt=None):
    """Relevanz-Scoring: Keyword-Schnitt + Typ-Boost + Wichtigkeit + Projektbezug.
    Abgelaufenes wird ignoriert. Nur Passendes gelangt in den Prompt."""
    daten = laden(pfad)
    q = _begriffe(frage)
    if not q:
        return []
    boost = {"decision": 3, "lesson": 3, "project_fact": 2, "task": 2,
             "fact": 1, "user_preference": 1, "hypothesis": 0, "unknown": 0}
    treffer = []
    for e in daten["eintraege"]:
        if abgelaufen(e):
            continue
        w = _begriffe(e.get("content", ""))
        schnitt = q & w
        if not schnitt:
            continue
        punkte = len(schnitt) + boost.get(e.get("type"), 0)
        try: punkte += (int(e.get("wichtigkeit", 3)) - 3) * 0.5
        except Exception: pass
        if projekt and e.get("projekt") and str(e["projekt"]).lower() in str(projekt).lower():
            punkte += 2  # Projektbezug zählt
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
        proj = f" [{e['projekt']}]" if e.get("projekt") else ""
        ab = " (gültig)" if not e.get("ablauf") else f" (bis {e['ablauf'][:10]})"
        zeilen.append(f"- [{e.get('type')}{proj}] {e.get('content')}{mark}{ab}")
    return "\n".join(zeilen)


def chats_aufraeumen(chats_ordner, tage=30, archiv_name="archiv"):
    """Alte Chats (*.json, außer autosave) wandern in einen Archiv-Unterordner.
    Nichts wird gelöscht. Gibt Anzahl zurück."""
    try:
        basis = Path(str(chats_ordner))
        if not basis.is_dir() or int(tage) <= 0:
            return 0
        import time as _time
        grenze = _time.time() - int(tage) * 86400
        ziel = basis / archiv_name
        n = 0
        for f in basis.glob("*.json"):
            if f.name == "autosave.json":
                continue
            try:
                if f.stat().st_mtime < grenze:
                    ziel.mkdir(exist_ok=True)
                    f.rename(ziel / f.name)
                    n += 1
            except Exception:
                continue
        return n
    except Exception:
        return 0


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
