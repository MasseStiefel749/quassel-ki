"""Beispiel-Plugin für Quassel-KI v9.
Eigene Plugins: Datei nach plugins/*.py kopieren, Funktion register(app) anbieten.
Zurück: {"tools": {name: fn(args_dict, ctx_dict) -> str}, "buttons": [(label, fn)]}.
ctx enthält: pc, sysinfo, projekt. Tools laufen über das MCP-Panel (mit Nachfrage).
"""
import random

try:
    from quassel_ki_v9 import UNREAL_TIPPS
except Exception:
    UNREAL_TIPPS = ["Tipp!"]

def register(app):
    def zufalls_tipp(args, ctx):
        return "Plugin-Tipp: " + random.choice(UNREAL_TIPPS)

    def rechner_kurz(args, ctx):
        s = ctx["sysinfo"]
        return (f"CPU-Kerne: {s['cpu']}, RAM: {s['ram']}GB, GPU: {s['gpu']}, "
                f"C: frei {s['disk_free']}GB, UE: {list(s['editors'].keys()) or '-'}")

    return {
        "tools": {"plugin_tipp": zufalls_tipp, "rechner_kurz": rechner_kurz},
        "buttons": [("🎲 Plugin-Tipp", lambda: app.bot_sagt(zufalls_tipp({}, {"sysinfo": app.sysinfo})))],
    }
