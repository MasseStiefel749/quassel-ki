# -*- coding: utf-8 -*-
"""Hardware-Profiler: erkennt GPU/VRAM/RAM/CPU/Ollama – ohne neue Dependencies."""
from __future__ import annotations
import ctypes
import json
import os
import platform
import shutil
import subprocess
import urllib.request


def _cmd(args, timeout=15):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def gpus():
    """Liste von {name, vram_mb, treiber}. Leer = keine NVIDIA-GPU."""
    out = _cmd(["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader,nounits"])
    karten = []
    for zeile in out.splitlines():
        teile = [t.strip() for t in zeile.split(",")]
        if len(teile) >= 2:
            try: vram = int(float(teile[1].replace("MiB", "").strip()))
            except Exception: vram = 0
            karten.append({"name": teile[0], "vram_mb": vram,
                           "treiber": teile[2] if len(teile) > 2 else ""})
    return karten


def ram_gb():
    try:
        class Status(ctypes.Structure):
            _fields_ = [("laenge", ctypes.c_ulong), ("speicherlast", ctypes.c_ulong),
                        ("total_phys", ctypes.c_ulonglong), ("avail_phys", ctypes.c_ulonglong),
                        ("total_page", ctypes.c_ulonglong), ("avail_page", ctypes.c_ulonglong),
                        ("total_virt", ctypes.c_ulonglong), ("avail_virt", ctypes.c_ulonglong),
                        ("avail_ext", ctypes.c_ulonglong)]
        st = Status(); st.laenge = ctypes.sizeof(Status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return round(st.total_phys / (1024 ** 3), 1), round(st.avail_phys / (1024 ** 3), 1)
    except Exception:
        pass
    return 0.0, 0.0


def cpu_name():
    try:  # Windows-Registry kennt den echten Namen (wmic gibt es oft nicht mehr)
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
            name, _ = winreg.QueryValueEx(k, "ProcessorNameString")
            if name: return str(name).strip()
    except Exception:
        pass
    return (platform.processor() or platform.machine() or "unbekannte CPU").strip()


def ollama_version():
    out = _cmd(["ollama", "--version"])
    return out.replace("ollama version is", "").replace("ollama version", "").strip() or "unbekannt"


def ollama_modelle():
    """Installiert: [{name, gb, parameter, quant}]. Geladen: [namen]."""
    installiert, geladen = [], []
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=10) as r:
            for m in json.loads(r.read().decode()).get("models", []):
                det = m.get("details", {}) or {}
                installiert.append({"name": m.get("name", ""),
                                    "gb": round((m.get("size", 0) or 0) / 1e9, 1),
                                    "parameter": det.get("parameter_size", "?"),
                                    "quant": det.get("quantization_level", "?")})
    except Exception:
        pass
    try:
        data = json.dumps({}).encode()
        req = urllib.request.Request("http://127.0.0.1:11434/api/ps", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            geladen = [m.get("name", "") for m in json.loads(r.read().decode()).get("models", [])]
    except Exception:
        pass
    return installiert, geladen


def profil():
    """Komplettes Hardware-Profil als Dict. Wirft nie (leere Felder bei Fehlern)."""
    total, frei = ram_gb()
    karten = gpus()
    vram = round(sum(k.get("vram_mb", 0) for k in karten) / 1024, 1)
    installiert, geladen = ollama_modelle()
    try: platte_frei = round(shutil.disk_usage(os.getcwd()).free / 1e9, 1)
    except Exception: platte_frei = 0.0
    if vram >= 10: kapazitaet = "HIGH"
    elif vram >= 5: kapazitaet = "MEDIUM"
    elif karten: kapazitaet = "LOW"
    else: kapazitaet = "CPU"
    return {"gpu": karten, "vram_gb": vram, "ram_total_gb": total,
            "ram_frei_gb": frei, "cpu": cpu_name(),
            "cpu_kerne": os.cpu_count() or 0, "os": platform.platform(),
            "cuda": "AVAILABLE" if karten else "NONE",
            "ollama": ollama_version(), "modelle_installiert": installiert,
            "modelle_geladen": geladen, "platte_frei_gb": platte_frei,
            "kapazitaet": kapazitaet,
            "modus": "LOCAL MAXIMUM INTELLIGENCE" if kapazitaet in ("HIGH", "MEDIUM") else "LOCAL ECO MODE"}


# Bekannte Karten mit Sonderverhalten (Name-Fragment -> Klasse). Sonst zählt nur VRAM.
# Begründung: Eine RTX 3060 12GB KANN 30B laden, ist dabei aber so langsam, dass
# 7–14B-Modelle praktisch mehr Intelligenz pro Sekunde liefern (siehe DECISIONS E8).
_KARTEN_KORREKTUR = (
    ("3060", "medium"),
    ("4060", "medium"),
    ("a1000", "small"),
    ("a2000", "medium"),
    ("t1000", "small"),
    ("t600", "small"),
    ("p1000", "small"),
    ("p620", "small"),
    ("mx", "small"),
    ("uhd", "cpu"),
    ("iris", "cpu"),
    ("radeon", "cpu"),  # kein CUDA -> CPU-Klasse (Ollama CPU/Vulkan je nach Build)
    ("vega", "cpu"),
)


def hardware_klasse(p=None):
    """high | medium | small | cpu. Basis: VRAM, korrigiert um bekannte Karten."""
    p = p or profil()
    vram = p.get("vram_gb", 0) or 0
    if vram >= 11:
        klasse = "high"
    elif vram >= 7:
        klasse = "medium"
    elif vram >= 4:
        klasse = "small"
    else:
        klasse = "cpu"
    namen = " ".join(g.get("name", "") for g in p.get("gpu", [])).lower()
    for fragment, korr in _KARTEN_KORREKTUR:
        if fragment in namen:
            rang = {"cpu": 0, "small": 1, "medium": 2, "high": 3}
            if rang[korr] < rang[klasse]:
                klasse = korr  # nur ABwärts korrigieren, nie aufwärts schummeln
            break
    return klasse


KLASSEN_EMPFEHLUNG = {
    "high": {"max_modell_gb": 21.0, "ctx": 16384, "ctx_max": 32768,
             "chat_tokens": 500, "keep_alive": "30m",
             "beschreibung": "Starkes Coding-Modell (bis ~20 GB), großer Kontext."},
    "medium": {"max_modell_gb": 10.0, "ctx": 8192, "ctx_max": 16384,
               "chat_tokens": 400, "keep_alive": "20m",
               "beschreibung": "7–14B quantisiert, mittlerer Kontext."},
    "small": {"max_modell_gb": 5.5, "ctx": 4096, "ctx_max": 8192,
              "chat_tokens": 300, "keep_alive": "15m",
              "beschreibung": "7B quantisiert, kleiner Kontext."},
    "cpu": {"max_modell_gb": 5.5, "ctx": 4096, "ctx_max": 4096,
            "chat_tokens": 250, "keep_alive": "10m",
            "beschreibung": "Kleines Modell auf CPU, sehr kleiner Kontext."},
}


def empfehlung(p=None):
    """Gibt {klasse, max_modell_gb, ctx, ctx_max, chat_tokens, keep_alive, beschreibung}.
    Reine Messung + Tabelle, kein Raten."""
    p = p or profil()
    klasse = hardware_klasse(p)
    erg = dict(KLASSEN_EMPFEHLUNG[klasse])
    erg["klasse"] = klasse
    # Viel RAM hebt den ctx-Deckel etwas (KV-Cache liegt teils in RAM)
    if (p.get("ram_total_gb", 0) or 0) >= 48 and erg["ctx_max"] < 32768:
        erg["ctx_max"] = min(32768, erg["ctx_max"] * 2)
    return erg


def profil_text(p=None):
    """Lesbarer Block für /status und Startbanner. Nur echte Messwerte."""
    p = p or profil()
    zeilen = ["QUASSEL HARDWARE", ""]
    if p["gpu"]:
        for i, g in enumerate(p["gpu"], 1):
            zeilen.append(f"GPU {i}: {g['name']} ({round(g['vram_mb']/1024,1)} GB VRAM)")
    else:
        zeilen.append("GPU: keine NVIDIA-GPU gefunden (CPU-Modus)")
    zeilen += [f"VRAM gesamt: {p['vram_gb']} GB",
               f"RAM: {p['ram_total_gb']} GB (frei {p['ram_frei_gb']} GB)",
               f"CPU: {p['cpu']} ({p['cpu_kerne']} Kerne)",
               f"CUDA: {p['cuda']}", f"Ollama: {p['ollama']}",
               f"Platte frei: {p['platte_frei_gb']} GB", "",
               "Modelle installiert:"]
    for m in p["modelle_installiert"]:
        mark = "●" if m["name"] in p["modelle_geladen"] else "○"
        zeilen.append(f"  {mark} {m['name']} ({m['gb']} GB, {m['parameter']}, {m['quant']})")
    if not p["modelle_installiert"]:
        zeilen.append("  (keine – Ollama läuft nicht oder leer)")
    zeilen += ["", f"MODEL CAPACITY: {p['kapazitaet']}", f"MODE: {p['modus']}"]
    return "\n".join(zeilen)


if __name__ == "__main__":
    import sys
    text = profil_text()
    try:
        print(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8", "replace"))
