# -*- coding: utf-8 -*-
"""Auftrags-Tracker (Phase 8): 3-Strikes-Regel, Checkpoints, Rollback.
Jede Aufgabe: max 3 Versuche, danach Stopp + dokumentierte Ursache."""
from __future__ import annotations
import subprocess
from datetime import datetime

MAX_VERSUCHE = 3


def _git(args, cwd, timeout=60):
    try:
        r = subprocess.run(["git"] + list(args), capture_output=True, text=True,
                           timeout=timeout, cwd=str(cwd),
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.returncode, (r.stdout or "").strip()
    except Exception as e:
        return 128, str(e)[:150]


def neuer_stand():
    return {"aufgaben": {}}


def eintrag(stand, task_id):
    aufgaben = stand.setdefault("aufgaben", {})
    return aufgaben.setdefault(str(task_id), {"versuche": 0, "fehler": [],
                                              "status": "offen", "seit": None})


def darf_nochmal(stand, task_id):
    e = eintrag(stand, task_id)
    return e["status"] not in ("fertig", "aufgegeben") and e["versuche"] < MAX_VERSUCHE


def fehlversuch(stand, task_id, grund):
    """Zählt hoch. Gibt True wenn aufgegeben (3 Strikes) – dann dokumentieren + nächste Aufgabe."""
    e = eintrag(stand, task_id)
    e["versuche"] += 1
    e["fehler"].append({"zeit": datetime.now().isoformat(timespec="seconds"),
                        "grund": str(grund)[:300]})
    e["fehler"] = e["fehler"][-5:]
    if e["versuche"] >= MAX_VERSUCHE:
        e["status"] = "aufgegeben"
        return True
    e["status"] = "offen"
    return False


def erfolg(stand, task_id, notiz=""):
    e = eintrag(stand, task_id)
    e["status"] = "fertig"
    if notiz:
        e["fehler"].append({"zeit": datetime.now().isoformat(timespec="seconds"),
                            "grund": "ERFOLG: " + str(notiz)[:300]})


def checkpoint_head(repo):
    code, out = _git(["rev-parse", "HEAD"], repo)
    return out if code == 0 else ""


def rollback(repo, head):
    """Rückrollmöglichkeit: harter Reset auf den Checkpoint-Stand.
    Nur auf eigenem Branch aufrufen (Find&Finish tut das)."""
    if not head:
        return False, "Kein Checkpoint-Stand bekannt."
    code, _ = _git(["rev-parse", "--is-shallow-repository"], repo)
    code, out = _git(["reset", "--hard", head], repo)
    if code != 0:
        return False, out or "Reset fehlgeschlagen."
    return True, f"Zurück auf {head[:8]}."


def geaenderte_dateien(repo, head):
    """Dateien seit Checkpoint (für Testnachweis)."""
    if not head:
        return []
    code, out = _git(["diff", "--name-only", head], repo)
    if code != 0:
        return []
    return [z for z in out.splitlines() if z.strip()][:20]
