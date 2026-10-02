# -*- coding: utf-8 -*-
"""Brain-Router-Kern: Rollen, Difficulty, Speed-Modes, Context-Budget. Reine Logik, kein Ollama."""
from __future__ import annotations

ROLLEN = ("fast", "coding", "reasoning", "vision", "fallback")

STANDARD_ROLLEN = {
    # Kandidaten in Priorität; Platzhalter {basis} wird nicht gebraucht – echte Namen aus Konfig/Erkennung
    "fast": ["llama3.1:latest", "llama3.1", "qwen3:8b", "qwen2.5:7b"],
    "coding": ["quassel-ki:latest", "quassel-ki", "qwen3-coder:30b", "qwen2.5-coder:32b",
               "qwen2.5-coder:14b", "qwen2.5-coder:7b"],
    "reasoning": ["quassel-ki:latest", "quassel-ki", "qwen3:32b", "qwen2.5:32b"],
    "vision": ["moondream:latest", "moondream", "llava:latest"],
    "fallback": ["llama3.1:latest", "llama3.1", "moondream:latest", "moondream"],
}

SCHWERE = ("TRIVIAL", "LOW", "MEDIUM", "HIGH", "MAX")

_CODE_WOERTER = {"code", "funktion", "klasse", "fehler", "bug", "traceback", "exception",
                 "kompilier", "build", "cpp", "h.", "python", "skript", "ue5", "unreal",
                 "actor", "blueprint", "niagara", "replikation", "shader", "crash", "log",
                 "def ", "class ", "include", "pointer", "nullptr"}
_FRAGE_KURZ = {"was ist", "wer ist", "wo ist", "wie spät", "wetter", "danke", "hallo",
               "hi", "hey", "ok", "okay", "ja", "nein", "bitte"}
_PLAN_WOERTER = {"architektur", "entwurf", "entwirf", "plane", "konzept", "strategie",
                 "roadmap", "mmo", "multiplayer", "server", "netzwerk", "analyse",
                 "analysiere", "vergleiche", "entscheide", "komplett", "gesamte"}


def schwierigkeit(text):
    """Heuristik ohne Modell (schnell, deterministisch). Gibt (stufe, begründung)."""
    t = (text or "").lower().strip()
    woerter = len(t.split())
    if not t or woerter <= 3 or any(t.startswith(k) for k in _FRAGE_KURZ):
        return "TRIVIAL", "sehr kurz / Smalltalk"
    code = sum(1 for w in _CODE_WOERTER if w and w in t)
    plan = sum(1 for w in _PLAN_WOERTER if w in t)
    if plan >= 2 or (plan >= 1 and woerter > 25) or woerter > 80:
        return ("MAX", "Projekt-/Architektur-Umfang") if woerter > 40 or plan >= 2 else ("HIGH", "Planung/Analyse")
    if code >= 2 or "```" in t or t.count("\n") > 4:
        return "MEDIUM", "Code-Kontext erkannt"
    if woerter <= 12:
        return "LOW", "kurze Frage"
    return "MEDIUM", "Standard"


def _norm(name):
    n = (name or "").lower()
    return n.split(":")[0] if ":" in n else n


def waehle_modell(rolle, installiert, rollen_konfig=None):
    """Bestes installiertes Modell für Rolle. Fallback-Kette, nie None wenn irgendwas da ist."""
    tabelle = rollen_konfig or STANDARD_ROLLEN
    inst = {_norm(n) for n in (installiert or [])}
    inst_voll = {(n or "").lower() for n in (installiert or [])}
    for kandidat in tabelle.get(rolle, []):
        if kandidat.lower() in inst_voll or _norm(kandidat) in inst:
            return kandidat if kandidat.lower() in inst_voll else next(
                (n for n in (installiert or []) if _norm(n) == _norm(kandidat)), kandidat)
    if rolle != "fallback":
        return waehle_modell("fallback", installiert, tabelle)
    return (installiert or [None])[0]


def speed_rolle(schwere_stufe, braucht_vision, braucht_code, speed_mode="SMART"):
    """Speed-Mode + Aufgabe -> Rolle. FAST zwingt schnell, MAXIMUM zwingt stark."""
    mode = (speed_mode or "SMART").upper()
    if braucht_vision:
        return "vision"
    if mode == "FAST":
        return "fast"
    if mode == "MAXIMUM":
        return "reasoning" if schwere_stufe in ("HIGH", "MAX") else "coding"
    if mode == "BALANCED":
        if schwere_stufe in ("TRIVIAL", "LOW"):
            return "fast"
        return "coding" if braucht_code else "reasoning" if schwere_stufe == "MAX" else "fast"
    # SMART
    if schwere_stufe in ("TRIVIAL", "LOW"):
        return "fast"
    if schwere_stufe == "MEDIUM":
        return "coding" if braucht_code else "fast"
    return "reasoning" if schwere_stufe == "MAX" else "coding"


def context_budget(schwere_stufe, ram_gb=16, modell_gb=19, speed_mode="SMART"):
    """Adaptives Kontext-Budget. Deckel: RAM (KV-Cache) + Modellgröße. Nie über 32k ohne Nachweis."""
    basis = {"TRIVIAL": 4096, "LOW": 4096, "MEDIUM": 8192, "HIGH": 16384, "MAX": 32768}
    budget = basis.get(schwere_stufe, 8192)
    if (ram_gb or 16) < 12 and budget > 8192:
        budget = 8192  # wenig RAM -> KV-Cache-Deckel
    if (modell_gb or 19) > 20 and budget > 16384:
        budget = 16384  # Riesenmodell + Riesenctx = Swap-Tod
    if (speed_mode or "SMART").upper() == "FAST" and budget > 8192:
        budget = 8192
    return budget


def braucht_vision_check(text):
    t = (text or "").lower()
    return any(k in t for k in ("screenshot", "bild", "foto", "screen", "sieh", "schau", "editor zeigt", "fehlermeldung"))


def entscheidungs_protokoll(text, speed_mode="SMART"):
    """Ein Aufruf für UI-Log: was der Router entschieden hat und warum."""
    stufe, warum = schwierigkeit(text)
    vision = braucht_vision_check(text)
    tl = (text or "").lower()
    code = any(w for w in _CODE_WOERTER if w and w in tl)
    rolle = speed_rolle(stufe, vision, code, speed_mode)
    return {"schwere": stufe, "warum": warum, "vision": vision, "code": code,
            "rolle": rolle, "speed": (speed_mode or "SMART").upper()}
