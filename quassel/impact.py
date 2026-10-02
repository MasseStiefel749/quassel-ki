# -*- coding: utf-8 -*-
"""Impact-Analyse (Phase 7): Was hängt an Klasse/Datei? Ehrliche Suche inkl.
Binär-Assets (Byte-Suche), Tests, Maps. Risiko LOW–CRITICAL. Schnell, ohne Modell."""
from __future__ import annotations
import re
from pathlib import Path

_TEXT_EXTS = {".h", ".cpp", ".hpp", ".cs", ".ini", ".uproject", ".uplugin",
              ".csproj", ".sln", ".py", ".json", ".md"}
_BIN_EXTS = {".uasset", ".umap"}
_SKIP = ("Intermediate", "Binaries", "DerivedDataCache", ".git", "node_modules", ".vs")


def _ist_text(datei):
    return datei.suffix.lower() in _TEXT_EXTS


def datei_risiko(pfad):
    """CRITICAL/HIGH allein aus dem Dateityp (Konfiguration, Projektdateien)."""
    n = str(pfad).lower().replace("\\", "/")
    if n.endswith((".uproject", ".sln", ".uplugin")):
        return "CRITICAL"  # kaputt = Projekt tot
    if "config/" in n:
        return "HIGH"
    if "saved" in n or "intermediate" in n:
        return "LOW"
    return ""


def analysieren(ordner, ziel, max_treffer=40):
    """Gibt {ziel, referenzen, module, tests, maps_assets, risiko, empfehlung}."""
    basis = Path(str(ordner))
    name = re.sub(r"\W", "", str(ziel or ""))
    erg = {"ziel": name, "referenzen": [], "module": [], "tests": [],
           "maps_assets": [], "risiko": "LOW", "empfehlung": "", "fehler": ""}
    if not name:
        erg["fehler"] = "Ziel fehlt."
        return erg
    if not basis.is_dir():
        erg["fehler"] = "Ordner fehlt."
        return erg
    stamm = name[1:] if name.startswith(("A", "U")) and len(name) > 2 else name
    for f in basis.rglob("*"):
        try:
            if not f.is_file() or any(s in str(f) for s in _SKIP):
                continue
            if f.stem == name or f.stem == stamm:
                continue  # eigene Datei ist keine Referenz
            rel = str(f.relative_to(basis))
            ext = f.suffix.lower()
            if _ist_text(f):
                if f.stat().st_size > 500000:
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
                if name in text or (stamm and stamm in text):
                    erg["referenzen"].append(rel)
                    niedrig = rel.lower()
                    if "test" in niedrig:
                        erg["tests"].append(rel)
            elif ext in _BIN_EXTS:
                try:
                    roh = f.read_bytes()[:200000]
                    if name.encode("utf-8", "ignore") in roh or (stamm and stamm.encode("utf-8", "ignore") in roh):
                        erg["maps_assets"].append(rel)
                except Exception:
                    continue
            if len(erg["referenzen"]) + len(erg["maps_assets"]) >= max_treffer:
                break
        except Exception:
            continue
    # Module = beteiligte Source-Unterordner (oder der Ordner selbst, wenn er ein Modul ist)
    module = set()
    for r in erg["referenzen"]:
        teile = Path(r).parts
        if "Source" in teile:
            i = teile.index("Source")
            if i + 1 < len(teile):
                module.add(teile[i + 1])
    if not module and basis.parent.name == "Source":
        module.add(basis.name)
    erg["module"] = sorted(module)
    n = len(erg["referenzen"]) + len(erg["maps_assets"])
    config_treffer = [r for r in erg["referenzen"] if r.lower().endswith((".ini", ".uproject", ".uplugin"))]
    if config_treffer or n >= 15:
        erg["risiko"] = "HIGH"
    elif n >= 5 or erg["maps_assets"]:
        erg["risiko"] = "MEDIUM"
    else:
        erg["risiko"] = "LOW"
    erg["empfehlung"] = {
        "LOW": "Umbau ok. Danach: betroffene Datei kompilieren/testen.",
        "MEDIUM": "Erst ändern, dann: Build + zugehörige Tests + betroffene Maps öffnen.",
        "HIGH": "NICHT autonom schreiben. Plan + Diff vorschlagen, Nutzer entscheidet. Danach Voll-Build + alle Tests.",
    }[erg["risiko"]]
    return erg


def bericht(a):
    z = [f"Impact {a['ziel']}: {len(a['referenzen'])} Referenzen, "
         f"{len(a['maps_assets'])} Maps/Assets, Module: {', '.join(a['module']) or '–'} "
         f"(Risiko {a['risiko']})"]
    for r in a["referenzen"][:20]:
        z.append(f"  • {r}")
    for r in a["maps_assets"][:10]:
        z.append(f"  ◆ Asset: {r}")
    if a["tests"]:
        z.append(f"  Tests betroffen: {', '.join(a['tests'][:5])}")
    z.append(f"Empfehlung: {a['empfehlung']}")
    return "\n".join(z)
