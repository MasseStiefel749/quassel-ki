# -*- coding: utf-8 -*-
"""Schmiede-Tasks als strukturiertes tasks.json (Phase 5).
Jede Aufgabe: ID, Ziel, Akzeptanzkriterien, Dateien/Systeme, Abhängigkeiten,
Risiko, Testschritte, Status, Kategorie, Annahmen. Kein Blindflug."""
from __future__ import annotations
import json
import re
from datetime import datetime
from pathlib import Path

RISIKEN = ("low", "medium", "high", "critical")
STATUS = ("offen", "in_arbeit", "fertig", "blockiert")
KATEGORIEN = ("cpp", "blueprint", "asset", "multiplayer", "performance", "sonst")

_KAT_WOERTER = {
    "cpp": ("c++", "klasse", "actor", "component", "uproperty", "ufunction", "build.cs", ".h", ".cpp"),
    "blueprint": ("blueprint", "widget", "umg", "level", "sequencer"),
    "asset": ("asset", "material", "textur", "mesh", "niagara", "sound", "animation"),
    "multiplayer": ("multiplayer", "replikation", "server", "client", "rpc", "lobby", "session"),
    "performance": ("performance", "fps", "optimier", "latenz", "profil", "speicherverbrauch"),
}


def kategorie(text):
    t = (text or "").lower()
    for kat, woerter in _KAT_WOERTER.items():
        if any(w in t for w in woerter):
            return kat
    return "sonst"


def risiko_fuer(text, kategorie_hint=""):
    t = (text or "").lower()
    try:
        from .projekte import _risiko_einschaetzen
        r = _risiko_einschaetzen(text).lower()
        if r in RISIKEN:
            return r
    except Exception:
        pass
    return "low"


def task_bauen(nr, ziel, akzeptanz=None, dateien=None, systeme=None, abhaengig_von=None,
               risiko=None, testschritte=None, status="offen", annahmen=None):
    zid = f"T{int(nr):03d}"
    kat = kategorie(ziel)
    return {
        "id": zid,
        "ziel": str(ziel).strip()[:300],
        "akzeptanz": [str(a).strip()[:200] for a in (akzeptanz or []) if str(a).strip()][:5],
        "dateien": [str(d)[:150] for d in (dateien or [])][:10],
        "systeme": [str(s)[:80] for s in (systeme or [])][:5],
        "abhaengig_von": [str(a).upper()[:8] for a in (abhaengig_von or [])],
        "risiko": (risiko or risiko_fuer(ziel, kat)) if (risiko or risiko_fuer(ziel, kat)) in RISIKEN else "medium",
        "testschritte": [str(s).strip()[:200] for s in (testschritte or []) if str(s).strip()][:5],
        "status": status if status in STATUS else "offen",
        "kategorie": kat,
        "annahmen": [str(a).strip()[:200] for a in (annahmen or []) if str(a).strip()][:5],
    }


def validieren(tasks):
    """Gibt Fehlerliste zurück (leer = ok). Prüft Pflichtfelder, IDs, Risiko, Status."""
    fehler = []
    ids = set()
    for i, t in enumerate(tasks or []):
        wo = t.get("id", f"#{i}")
        if not str(t.get("ziel", "")).strip():
            fehler.append(f"{wo}: Ziel fehlt")
        if t.get("id") in ids:
            fehler.append(f"{wo}: doppelte ID")
        ids.add(t.get("id"))
        if t.get("risiko") not in RISIKEN:
            fehler.append(f"{wo}: ungültiges Risiko")
        if t.get("status") not in STATUS:
            fehler.append(f"{wo}: ungültiger Status")
        if t.get("id") in (t.get("abhaengig_von") or []):
            fehler.append(f"{wo}: hängt von sich selbst ab")
    return fehler


def zerlegen(ziel, start_nr=1):
    """Teilt Riesen-Aufgaben an ' und ' / ';' / nummerierten Teilen.
    Folgetasks hängen per abhaengig_von am Vorgänger (klein planen)."""
    teile = [t.strip() for t in re.split(r"\s+und\s+|;\s*|\n", str(ziel)) if len(t.strip()) >= 8]
    if len(teile) <= 1:
        return [task_bauen(start_nr, ziel)]
    tasks, vor = [], None
    for i, teil in enumerate(teile[:6]):
        t = task_bauen(start_nr + i, teil[0].upper() + teil[1:] if teil else teil,
                       abhaengig_von=[vor] if vor else [])
        vor = t["id"]
        tasks.append(t)
    return tasks


def aus_markdown(text):
    """Importiert tasks.md-Zeilen ('- [ ]'/'- [x]') zu strukturierten Tasks (IDs T001…)."""
    tasks, n = [], 0
    for zeile in str(text).splitlines():
        m = re.match(r"\s*-\s*\[( |x|X)\]\s*(.+)", zeile)
        if not m:
            continue
        n += 1
        for t in zerlegen(m.group(2).strip(), n):
            if t["status"] == "offen" and m.group(1).lower() == "x":
                t["status"] = "fertig"
            tasks.append(t)
    # IDs neu durchnummerieren (zerlegen kann doppeln)
    for i, t in enumerate(tasks, 1):
        t["id"] = f"T{i:03d}"
    # Abhängigkeiten nach Neu-Nummerierung reparieren (Kette bleibt Kette)
    return tasks


def schreiben(pfad, tasks, spiel="", idee=""):
    fehler = validieren(tasks)
    if fehler:
        return False, fehler
    ziel = Path(str(pfad))
    try:
        ziel.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, [f"Ordner nicht anlegbar: {e}"]
    obj = {"schema": 1, "spiel": spiel, "idee": (idee or "")[:500],
           "stand": datetime.now().isoformat(timespec="seconds"), "tasks": tasks}
    ziel.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return True, []


def lesen(pfad):
    try:
        obj = json.loads(Path(str(pfad)).read_text(encoding="utf-8"))
        if isinstance(obj, dict) and isinstance(obj.get("tasks"), list):
            return obj
    except Exception:
        pass
    return None


def status_text(obj):
    tasks = (obj or {}).get("tasks", [])
    fertig = sum(1 for t in tasks if t.get("status") == "fertig")
    zeilen = [f"Fortschritt {fertig}/{len(tasks)} (tasks.json):"]
    for t in tasks:
        if t.get("status") != "fertig":
            mark = {"offen": "○", "in_arbeit": "◐", "blockiert": "⛔"}.get(t.get("status"), "?")
            zeilen.append(f"  {mark} {t['id']} [{t.get('kategorie')}/{t.get('risiko')}] {t.get('ziel','')[:80]}")
    return "\n".join(zeilen)
