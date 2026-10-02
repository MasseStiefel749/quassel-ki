# -*- coding: utf-8 -*-
"""Build/Test-Adapter (Phase 6): Befehle bauen (ohne Shell), Läufe loggen,
Fehler extrahieren, konkrete nächste Schritte liefern. Kein Raten."""
from __future__ import annotations
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ARTEN = ("python_test", "python_skript", "ue_build", "ue_test")

# Niemals ausführen, auch nicht mit Freigabe (Schutz vor Prompt-Injection in Logs)
_BLOCKLISTE = (r"rm\s+-rf\s+/", r"format\s+[a-z]:", r"mkfs", r"del\s+.*system32",
               r"rd\s+/s.*windows", r"drop\s+table", r":\(\)\{\s*:\|:\&\s*\};:")


def _blockiert(text):
    for pat in _BLOCKLISTE:
        if re.search(pat, str(text), re.IGNORECASE):
            return pat
    return ""


def ue_pfad_finden(dateiname="UnrealBuildTool.exe"):
    """Sucht UBT/RunUAT an Standardorten + UNREAL_ENGINE. None = nicht verfügbar (ehrlich)."""
    kandidaten = []
    env = __import__("os").environ.get("UNREAL_ENGINE", "")
    if env:
        kandidaten.append(Path(env))
    for basis in ("C:/Program Files/Epic Games", "D:/Epic Games", "C:/Unreal"):
        try:
            p = Path(basis)
            if p.is_dir():
                for ue in sorted(p.glob("UE_*")):
                    kandidaten.append(ue)
        except Exception:
            continue
    for ue in kandidaten:
        for treffer in (ue / "Engine/Binaries/DotNET/UnrealBuildTool" / dateiname,
                        ue / "Engine/Build/BatchFiles/RunUAT.bat"):
            try:
                if treffer.is_file():
                    return str(treffer)
            except Exception:
                continue
    return ""


def befehl_bauen(art, ziel, engine_pfad=""):
    """Baut exakte Befehlslisten (shell=False). Gibt (ok, befehl|grund)."""
    z = str(ziel or "")
    if _blockiert(z):
        return False, "Blockiert (Sicherheitsliste)."
    if art == "python_test":
        import shutil as _sh
        if _sh.which("pytest"):
            return True, [sys.executable, "-m", "pytest", z or ".", "-q"]
        return True, [sys.executable, "-m", "unittest", "discover", "-s", z or "."]
    if art == "python_skript":
        if not z.lower().endswith(".py"):
            return False, "Nur .py-Dateien."
        return True, [sys.executable, z]
    if art in ("ue_build", "ue_test"):
        ubt = engine_pfad or ue_pfad_finden()
        if not ubt:
            return False, "UnrealBuildTool nicht gefunden (keine UE-Installation) – als 'nicht verfügbar' melden, nicht raten."
        if art == "ue_build":
            return True, [ubt, "-projectfiles", f"-project={z}", "-game", "-engine"]
        return True, [ubt.replace("UnrealBuildTool.exe", "RunUAT.bat") if ubt.endswith(".exe") else ubt,
                      "RunUnreal", f"-project={z}"]
    return False, f"Unbekannte Art (erlaubt: {', '.join(ARTEN)})."


def lauf(art, ziel, cwd="", timeout=300, log_ordner="logs"):
    """Führt aus, loggt mit Zeitstempel, analysiert. Gibt Dict (BESTÄTIGT durch Exit-Code)."""
    ok, befehl = befehl_bauen(art, ziel)
    if not ok:
        return {"ok": False, "exit": None, "grund": befehl, "log": "", "analyse": {}}
    try:
        Path(log_ordner).mkdir(parents=True, exist_ok=True)
        log_pfad = str(Path(log_ordner) / f"lauf_{art}_{datetime.now():%Y%m%d_%H%M%S_%f}.log")
        r = subprocess.run(befehl, capture_output=True, text=True, timeout=int(timeout),
                           cwd=str(cwd or None) if cwd else None,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        ausgabe = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
        Path(log_pfad).write_text(f"$ {' '.join(befehl)}\nExit: {r.returncode}\n\n{ausgabe[-60000:]}",
                                  encoding="utf-8", errors="replace")
        analyse = analysieren(ausgabe)
        analyse["exit"] = r.returncode
        return {"ok": r.returncode == 0, "exit": r.returncode, "grund": "",
                "log": log_pfad, "analyse": analyse}
    except subprocess.TimeoutExpired:
        return {"ok": False, "exit": None, "grund": f"Timeout nach {timeout}s (Prozess gekillt).",
                "log": "", "analyse": {"fehler": ["Timeout"], "warnungen": [], "dateien": [],
                                       "ursache": "Lauf hing fest.", "schritte": ["Timeout erhöhen oder Teilschritt wählen."]}}
    except Exception as e:
        return {"ok": False, "exit": None, "grund": str(e)[:200], "log": "", "analyse": {}}


_FEHLER_MUSTER = (r"error", r"fatal", r"exception", r"failed", r"traceback", r"LNK\d+",
                  r"error C\d+", r"Cannot open", r"undefined reference", r"Assertion")
_WARN_MUSTER = (r"warning", r"warnung", r"deprecated")
_DATEI_MUSTER = re.compile(r"([A-Za-z0-9_\-./\\]+\.(?:cpp|h|hpp|cs|py|ini|uproject|uplugin|csproj))(?::|\s*\()", re.I)


def analysieren(text):
    """Extrahiert Fehler, Warnungen, Dateien + wahrscheinliche Ursache (Heuristik, ehrlich markiert)."""
    fehler, warnungen, dateien = [], [], []
    for zeile in str(text).splitlines():
        z = zeile.strip()
        if len(z) > 400 or not z:
            continue
        if re.search("|".join(_FEHLER_MUSTER), z, re.I):
            if len(fehler) < 15:
                fehler.append(z[:220])
        elif re.search("|".join(_WARN_MUSTER), z, re.I):
            if len(warnungen) < 10:
                warnungen.append(z[:220])
        for m in _DATEI_MUSTER.finditer(z):
            d = m.group(1)
            if d not in dateien and len(dateien) < 10:
                dateien.append(d)
    t = str(text)
    if re.search(r"Cannot open include|No such file.*\.h|fatal error C1083", t, re.I):
        ursache = "Header/Modul fehlt (Include-Pfad oder Build.cs prüfen)."
    elif re.search(r"LNK2005|LNK2038|doppelt definiert|multiple definition", t, re.I):
        ursache = "Linker-Konflikt (Doppeldefinition, Build-Artefakte löschen)."
    elif re.search(r"ModuleNotFound|ImportError|No module named", t, re.I):
        ursache = "Python-Paket fehlt (pip install / venv prüfen)."
    elif re.search(r"AssertionError|FAILED|assert", t, re.I):
        ursache = "Test-Logik schlägt fehl (Test + betroffene Funktion lesen)."
    elif re.search(r"Couldn't find|Failed to load.*uasset", t, re.I):
        ursache = "Asset-Referenz kaputt (Redirectors fixen, Asset suchen)."
    elif re.search(r"Super::|must be called|override", t, re.I):
        ursache = "Vererbungsfehler (Super-Aufruf / Signatur prüfen)."
    elif fehler:
        ursache = "Unbekannt – ersten Fehler oben lesen (nicht raten)."
    else:
        ursache = "Keine Fehler gefunden."
    return {"fehler": fehler, "warnungen": warnungen, "dateien": dateien,
            "ursache": ursache, "schritte": naechste_schritte({"fehler": fehler, "ursache": ursache, "dateien": dateien})}


def naechste_schritte(analyse):
    """Konkrete nächste Schritte statt nur Logtext."""
    schritte = []
    for d in (analyse.get("dateien") or [])[:3]:
        schritte.append(f"Datei lesen: {d}")
    u = analyse.get("ursache", "")
    if u and u != "Keine Fehler gefunden.":
        schritte.append(f"Ursache angehen: {u}")
    if not analyse.get("fehler"):
        return ["Keine Fehler – weiter geht's."]
    schritte.append("Fix einbauen (minimal, 1 Datei), dann Test/Build erneut laufen lassen.")
    return schritte[:6]


def bericht(erg):
    a = erg.get("analyse", {})
    zeilen = [f"Lauf: {'OK' if erg.get('ok') else 'FEHLGESCHLAGEN'} (Exit {erg.get('exit')})"]
    if erg.get("log"):
        zeilen.append(f"Log: {erg['log']}")
    if erg.get("grund"):
        zeilen.append(f"Grund: {erg['grund']}")
    if a.get("fehler"):
        zeilen += ["Fehler:"] + [f"  ! {f}" for f in a["fehler"][:8]]
    zeilen.append(f"Ursache (Heuristik): {a.get('ursache', '?')}")
    zeilen += ["Nächste Schritte:"] + [f"  → {s}" for s in naechste_schritte(a)]
    return "\n".join(zeilen)
