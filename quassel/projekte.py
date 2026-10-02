# -*- coding: utf-8 -*-
"""Projekt-Scanner + Task-Discovery. Erkennt Projekte, baut Metadaten-Index, findet Aufgaben.
Scannt NUR konfigurierte Verzeichnisse (niemals den ganzen Rechner)."""
from __future__ import annotations
import json
import os
import re
from datetime import datetime
from pathlib import Path

# Projekttyp -> Marker (Datei/Ordner relativ zum Projektroot)
TYP_MARKER = {
    "unreal": [".uproject", "Source/", "Content/", "Config/"],
    "python": ["pyproject.toml", "requirements.txt", "setup.py", ".py"],
    "node": ["package.json", "src/", "node_modules/"],
    "cpp": ["CMakeLists.txt", ".cpp", ".h"],
    "rust": ["Cargo.toml", "src/"],
    "csharp": [".sln", ".csproj", ".cs"],
    "java": ["pom.xml", "build.gradle", ".java"],
}

DOKU_DATEIEN = ["README.md", "ROADMAP.md", "TODO.md", "TASKS.md", "PLAN.md",
                "ARCHITECTURE.md", "CHANGELOG.md", "CONTRIBUTING.md", "QUASSEL.md",
                "AGENTS.md", "CLAUDE.md", "GEMINI.md", "PROJECT_RULES.md", "RULES.md"]

# Aufgaben-Marker: (Muster, starker Marker?)
AUFGABEN_MARKER = [
    (r"\bTODO\b", True), (r"\bFIXME\b", True), (r"\bXXX\b", True),
    (r"\bHACK\b", False), (r"\bWIP\b", False), (r"\bOPEN\b", False),
    (r"\bPLANNED\b", False), (r"\bNEXT\b", False), (r"\bNOT IMPLEMENTED\b", True),
    (r"\bMISSING\b", False), (r"\bIMPLEMENT\b", False),
    (r"\bNOCH ZU MACHEN\b", True), (r"\bOFFEN\b", False), (r"\bFEHLT\b", False),
    (r"\bIMPLEMENTIEREN\b", False), (r"\bERLEDIGEN\b", False), (r"\bGEPLANT\b", False),
]
_ZUKUNFT = re.compile(r"\b(maybe|vielleicht|idee|idea|someday|irgendwann|später|future|könnte man)\b", re.I)

_RISK_HIGH_W = ("build-system", "netzwerk", "datenbank", "migration", "architektur",
                "server", "replikation", "sicherheit", "auth", "payment", "zahlung")
_RISK_CRIT_W = ("löschen", "delete", "rm -rf", "format", "drop table", "passwort",
                "geheimnis", "secret", "os-", "betriebssystem", "registry")
_RISK_MED_W = ("gameplay", "config", "konfiguration", "mehrere dateien", "refactor",
               "ui", "hud", "input", "speichern", "save")


def _ist_projekt(ordner):
    p = Path(ordner)
    dateien = set()
    try:
        for kind in p.iterdir():
            dateien.add(kind.name)
            if kind.is_dir():
                dateien.add(kind.name + "/")
    except Exception:
        return None, []
    treffer = {}
    for typ, marker in TYP_MARKER.items():
        punkte = 0
        for m in marker:
            if m.endswith("/"):
                if m in dateien: punkte += 1
            elif m.startswith(".") and len(m) <= 5 and "*" not in m:
                if any(d == m or d.endswith(m) for d in dateien): punkte += 2
            else:
                if m in dateien: punkte += 2
        if punkte:
            treffer[typ] = punkte
    # Einzeldatei-Typen (.py/.cpp/.h) brauchen zusätzlich Masse
    for typ in ("python", "cpp"):
        if treffer.get(typ, 0) <= 1:
            try: n = sum(1 for _ in p.rglob("*.py" if typ == "python" else "*.cpp"))
            except Exception: n = 0
            if n >= 3: treffer[typ] = treffer.get(typ, 0) + 1
            elif typ in treffer and treffer[typ] <= 1: del treffer[typ]
    if not treffer:
        return None, []
    best = max(treffer, key=lambda k: treffer[k])
    return best, sorted(treffer)


def _engine_version(projekt_pfad):
    try:
        for up in Path(projekt_pfad).glob("*.uproject"):
            obj = json.loads(up.read_text(encoding="utf-8", errors="replace"))
            return str(obj.get("EngineAssociation", "")).strip("{} "), up.name
    except Exception:
        pass
    return "", ""


def _dokus(ordner):
    gefunden = {}
    try:
        for name in DOKU_DATEIEN:
            p = Path(ordner) / name
            if p.is_file():
                try:
                    if p.stat().st_size <= 200000:
                        gefunden[name] = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
        docs_dir = Path(ordner) / "docs"
        if docs_dir.is_dir():
            for f in sorted(docs_dir.glob("*.md"))[:10]:
                try:
                    if f.stat().st_size <= 200000:
                        gefunden[f"docs/{f.name}"] = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
    except Exception:
        pass
    return gefunden


def _risiko_einschaetzen(text):
    t = text.lower()
    if any(w in t for w in _RISK_CRIT_W):
        return "CRITICAL"
    if any(w in t for w in _RISK_HIGH_W):
        return "HIGH"
    if any(w in t for w in _RISK_MED_W):
        return "MEDIUM"
    return "LOW"


def _confidence(text, stark, quelle):
    """Hoch bei klarer Anweisung, niedrig bei vagen Ideen. Ehrlich, nicht geraten."""
    c = 0.9 if stark else 0.6
    if quelle != "doku":
        c -= 0.1
    if _ZUKUNFT.search(text):
        c -= 0.45
    if len(text.split()) < 3:
        c -= 0.2
    if re.search(r"\b(nie|kein|nicht)\b.*\b(tun|machen|ändern)\b", text, re.I):
        c -= 0.3  # klingt nach Verbot, nicht Auftrag
    return round(max(0.05, min(0.98, c)), 2)


def _tasks_aus_text(text, quelle, datei=""):
    tasks = []
    for nr, zeile in enumerate(str(text).splitlines(), 1):
        z = zeile.strip().strip("-*#> ").strip()
        if len(z) < 4 or len(z) > 300:
            continue
        gefunden = False
        for muster, stark in AUFGABEN_MARKER:
            if re.search(muster, zeile, re.I):
                inhalt = re.sub(muster, "", zeile, flags=re.I).strip(" :-\t")
                if len(inhalt) < 4:
                    inhalt = z
                tasks.append({
                    "text": inhalt[:250],
                    "quelle": quelle,
                    "datei": datei,
                    "zeile": nr,
                    "confidence": _confidence(inhalt, stark, quelle),
                    "risk": _risiko_einschaetzen(inhalt),
                })
                gefunden = True
                break
        if not gefunden and quelle == "doku" and 15 <= len(z) <= 200 and _ZUKUNFT.search(z):
            # Vage Zukunftsidee: erkennen, aber ehrlich niedrig bewerten (nie auto-ausführen)
            tasks.append({"text": z[:250], "quelle": quelle, "datei": datei, "zeile": nr,
                          "confidence": 0.25, "risk": "LOW"})
    return tasks


def _tasks_aus_code(ordner, max_dateien=60):
    tasks = []
    exts = {".py", ".cpp", ".h", ".hpp", ".cs", ".js", ".ts", ".rs", ".java", ".gd"}
    n = 0
    try:
        for f in Path(ordner).rglob("*"):
            if n >= max_dateien:
                break
            try:
                if not (f.is_file() and f.suffix.lower() in exts and f.stat().st_size <= 200000):
                    continue
                if any(x in str(f) for x in ("node_modules", ".git/", "Intermediate", "Binaries")):
                    continue
                n += 1
                text = f.read_text(encoding="utf-8", errors="replace")
                for t in _tasks_aus_text(text, "code", str(f.relative_to(ordner))):
                    tasks.append(t)
            except Exception:
                continue
    except Exception:
        pass
    return tasks


def projekt_analysieren(ordner):
    """Vollanalyse eines Projektordners -> Index-Dict (nur Metadaten + Verweise)."""
    ordner = str(ordner)
    typ, alle_typen = _ist_projekt(ordner)
    engine, uproject = _engine_version(ordner) if typ == "unreal" else ("", "")
    dokus = _dokus(ordner)
    tasks = []
    for name, inhalt in dokus.items():
        tasks += _tasks_aus_text(inhalt, "doku", name)
    tasks += _tasks_aus_code(ordner)
    regeln = [n for n in dokus if n.upper() in ("AGENTS.MD", "QUASSEL.MD", "PROJECT_RULES.MD", "RULES.MD", "CLAUDE.MD", "GEMINI.MD")]
    wichtige = [n for n in ("README.md", "ROADMAP.md", "TODO.md", "TASKS.md") if n in dokus]
    return {
        "name": Path(ordner).name,
        "pfad": ordner,
        "typ": typ or "unbekannt",
        "typ_kandidaten": alle_typen,
        "engine_version": engine,
        "uproject": uproject,
        "git": (Path(ordner) / ".git").is_dir(),
        "last_scan": datetime.now().isoformat(timespec="seconds"),
        "dokus": sorted(dokus),
        "regeln": regeln,
        "wichtige_dokus": wichtige,
        "tasks": sorted(tasks, key=lambda t: (-t["confidence"], t["risk"])),
    }


def scan_verzeichnisse(verzeichnisse, tiefe=2):
    """Findet Projekte in den gegebenen Ordnern (tiefe Ebenen). Gibt Index-Liste."""
    gefunden = []
    gesehen = set()
    for basis in verzeichnisse or []:
        try:
            root = Path(str(basis)).expanduser()
            if not root.is_dir():
                continue
            kandidaten = [root] + [k for k in root.iterdir() if k.is_dir()]
            if tiefe >= 2:
                for k in list(kandidaten[1:]):
                    try: kandidaten += [u for u in k.iterdir() if u.is_dir()]
                    except Exception: continue
            for k in kandidaten:
                try: key = str(k.resolve())
                except Exception: continue
                if key in gesehen:
                    continue
                gesehen.add(key)
                typ, _ = _ist_projekt(key)
                if typ:
                    try: gefunden.append(projekt_analysieren(key))
                    except Exception: continue
        except Exception:
            continue
    return sorted(gefunden, key=lambda p: p["name"].lower())


def top_tasks(index_liste, min_confidence=0.8, max_risk="MEDIUM", limit=10):
    """Sichere, konkrete Aufgaben über alle Projekte – sortiert nach Confidence."""
    rang = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    deckel = rang.get(max_risk, 1)
    alle = []
    for p in index_liste:
        for t in p.get("tasks", []):
            if t.get("confidence", 0) >= min_confidence and rang.get(t.get("risk", "HIGH"), 3) <= deckel:
                alle.append({"projekt": p["name"], "pfad": p["pfad"], **t})
    alle.sort(key=lambda t: -t["confidence"])
    return alle[:limit]


def tasks_bericht(index_liste, limit_projekte=5, limit_tasks=6):
    zeilen = []
    for p in index_liste[:limit_projekte]:
        extra = f" (UE {p['engine_version']})" if p.get("engine_version") else ""
        git = " +git" if p.get("git") else ""
        zeilen.append(f"📁 {p['name']} [{p['typ']}{extra}{git}] – {len(p['tasks'])} Aufgaben")
        if p.get("regeln"):
            zeilen.append(f"   Regeln: {', '.join(p['regeln'])} (werden vor Änderungen gelesen)")
        for t in p["tasks"][:limit_tasks]:
            wo = f" ({t['datei']}:{t['zeile']})" if t.get("datei") else ""
            zeilen.append(f"   [{t['risk']}/{t['confidence']:.2f}] {t['text'][:90]}{wo}")
    return "\n".join(zeilen) if zeilen else "Keine Projekte gefunden."
