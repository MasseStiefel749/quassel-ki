# -*- coding: utf-8 -*-
"""Quassel-Benchmark: misst ECHTE Werte (Ladezeit, tok/s, Mini-Tasks). Kein Fake.
Aufruf: python quassel_benchmark.py [modell ...]   (ohne Angabe: alle Rollen-Modelle)
Ergebnis: logs/benchmark_<datum>.json"""
import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

SYS = Path(__file__).resolve().parent
sys.path.insert(0, str(SYS))
from quassel import hardware, konfig

URL = "http://127.0.0.1:11434/api/chat"
LOG_DIR = SYS / "logs"
CFG = konfig.laden(SYS / "quassel.yaml")

MINI_TASKS = [
    {"name": "faktenfrage", "prompt": "Antworte mit genau einem Wort: Wie heißt die Hauptstadt von Deutschland?",
     "pruef": lambda t: "berlin" in t.lower()},
    {"name": "json_format", "prompt": "Gib NUR dieses JSON zurück, nichts davor oder danach: {\"ok\": true}",
     "pruef": lambda t: '"ok"' in t and "true" in t.lower()},
    {"name": "code_mini", "prompt": "Python, nur Code, keine Erklärung: Funktion add(a, b) die summiert.",
     "pruef": lambda t: re.search(r"def\s+add\s*\(", t) is not None},
]


def anfrage(modell, nachrichten, timeout=300, tokens=120, keep_alive="10m"):
    payload = {"model": modell, "messages": nachrichten, "stream": False,
               "keep_alive": keep_alive,
               "options": {"num_predict": tokens, "temperature": 0}}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    start = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        o = json.loads(r.read().decode())
    return o, time.time() - start


def modell_messen(modell):
    erg = {"modell": modell, "tasks": [], "fehler": None}
    try:
        # 1. Kaltladen: keep_alive 0 entlädt, dann messen wir echtes Laden
        try:
            anfrage(modell, [{"role": "user", "content": "hi"}], timeout=60, tokens=2, keep_alive="0")
        except Exception:
            pass
        o, wand = anfrage(modell, [{"role": "user", "content": "Antworte mit: bereit"}], timeout=600, tokens=10)
        erg["ladezeit_s"] = round((o.get("load_duration", 0) or 0) / 1e9, 1)
        erg["antwort_bereit_s"] = round(wand, 1)
        # 2. Durchsatz am warmen Modell
        o2, _ = anfrage(modell, [{"role": "user", "content": "Zähle von 1 bis 30, nur Zahlen mit Komma."}],
                        timeout=600, tokens=120)
        eval_s = (o2.get("eval_duration", 0) or 1) / 1e9
        eval_n = o2.get("eval_count", 0) or 0
        erg["tok_s"] = round(eval_n / eval_s, 1) if eval_s > 0 else 0.0
        erg["eval_count"] = eval_n
        # 3. Mini-Tasks (Qualität = bestanden/nicht, kein erfundener Score)
        for t in MINI_TASKS:
            try:
                o3, _ = anfrage(modell, [{"role": "user", "content": t["prompt"]}], timeout=600, tokens=150)
                text = o3.get("message", {}).get("content", "")
                ok = bool(t["pruef"](text))
            except Exception:
                ok, text = False, ""
            erg["tasks"].append({"name": t["name"], "bestanden": ok})
        erg["tasks_bestanden"] = sum(1 for t in erg["tasks"] if t["bestanden"])
    except Exception as e:
        erg["fehler"] = f"{type(e).__name__}: {e}"[:200]
    return erg


def haupt():
    gewuenscht = sys.argv[1:]
    if not gewuenscht:
        rollen = CFG.get("modelle", {}).get("rollen", {})
        reihenfolge = []
        for kandidaten in rollen.values():
            for k in kandidaten:
                if k not in reihenfolge:
                    reihenfolge.append(k)
        installiert = {m["name"] for m in hardware.profil()["modelle_installiert"]}
        gewuenscht = [m for m in reihenfolge if m in installiert or m.split(":")[0] in
                      {i.split(":")[0] for i in installiert}]
    print(f"Benchmark: {', '.join(gewuenscht)} (dauert pro großem Modell mehrere Minuten)")
    ergebnisse = {"zeit": datetime.now().isoformat(timespec="seconds"),
                  "hardware": {k: hardware.profil()[k] for k in
                               ("vram_gb", "ram_total_gb", "cpu", "cpu_kerne", "kapazitaet")},
                  "modelle": []}
    for m in gewuenscht:
        print(f"... messe {m}")
        ergebnisse["modelle"].append(modell_messen(m))
    LOG_DIR.mkdir(exist_ok=True)
    pfad = LOG_DIR / f"benchmark_{datetime.now():%Y%m%d_%H%M%S}.json"
    pfad.write_text(json.dumps(ergebnisse, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nGespeichert: {pfad.name}")
    for e in ergebnisse["modelle"]:
        if e.get("fehler"):
            print(f"  {e['modell']}: FEHLER {e['fehler']}")
        else:
            print(f"  {e['modell']}: laden {e['ladezeit_s']}s, {e['tok_s']} tok/s, "
                  f"tasks {e['tasks_bestanden']}/{len(e['tasks'])}")


if __name__ == "__main__":
    haupt()
