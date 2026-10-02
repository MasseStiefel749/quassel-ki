#!/usr/bin/env python3
"""
Quassel-KI v11 - Codex-Look mit Ansichten (Chat/Tools/Agent), Live-Agent, Sessions.
Start: python quassel_ki_v11.py
"""
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, filedialog
import random, time, threading, queue, re, os, json, shutil, subprocess, sys
import urllib.request, asyncio, tempfile, base64, difflib
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(r"C:\Users\S-Lasarzewski\Documents\Default Project")
ALLOWED_ROOTS = [
    WORKSPACE,
    Path.home() / "Documents" / "Unreal Projects",
    Path.home() / "Documents" / "Default Project",
    Path(os.environ.get("TEMP", r"C:\Temp")),
]
# ---------- Stimme v6: Neural (Edge) + Windows-Fallback ----------
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
try:
    import edge_tts as _edge_tts
    EDGE_OK = True
except ImportError:
    EDGE_OK = False
try:
    import pygame as _pygame
    PYGAME_OK = True
except ImportError:
    PYGAME_OK = False

STIMMEN = {
    "Katja (weiblich, neural)": "de-DE-KatjaNeural",
    "Conrad (männlich, neural)": "de-DE-ConradNeural",
    "Seraphina (weiblich, neural)": "de-DE-SeraphinaMultilingualNeural",
    "Florian (männlich, neural)": "de-DE-FlorianMultilingualNeural",
    "Windows (offline)": "windows",
}

class Sprecher:
    """Gescheite Stimme: Edge-Neural wenn möglich, sonst Windows-Offline. Liest ALLES vor."""
    CHUNK = 220
    def __init__(self):
        self.q = queue.Queue(); self.aktiv = True; self.enabled = True; self.rate = 175
        self.stumm = False  # v20-Phase3: absolute Stille (MUTE), gilt für ALLE Aufrufe
        self.stimme = "de-DE-KatjaNeural"
        self.backend = "edge" if (EDGE_OK and PYGAME_OK) else "windows"
        self.engine = None
        self._mixer_ok = False
        threading.Thread(target=self._loop, daemon=True).start()
    def _edge_sagen(self, text):
        async def _run():
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3"); tmp.close()
            tempo = "+0%" if self.rate == 175 else (f"+{int((self.rate-175)/1.75)}%" if self.rate > 175 else f"{int((self.rate-175)/1.75)}%")
            await _edge_tts.Communicate(text, self.stimme, rate=tempo).save(tmp.name)
            return tmp.name
        return asyncio.run(_run())
    def _loop(self):
        if PYGAME_OK:
            try: _pygame.mixer.init(); self._mixer_ok = True
            except Exception as e: print("Mixer:", e)
        if TTS_AVAILABLE:
            try:
                self.engine = pyttsx3.init()
                try:
                    for v in self.engine.getProperty('voices'):
                        n = (v.name + v.id).lower()
                        if 'hedda' in n or 'de-de' in n or 'german' in n or 'deutsch' in n:
                            self.engine.setProperty('voice', v.id); break
                except Exception: pass
            except Exception as e: print("TTS init:", e)
        engine = self.engine
        while self.aktiv:
            try: text = self.q.get(timeout=0.5)
            except queue.Empty: continue
            if not self.enabled or not text: continue
            gesprochen = False
            if self.backend == "edge" and EDGE_OK and self._mixer_ok and self.stimme != "windows":
                try:
                    datei = self._edge_sagen(text)
                    try:
                        _pygame.mixer.music.load(datei); _pygame.mixer.music.play()
                        while _pygame.mixer.music.get_busy() and self.aktiv and self.enabled:
                            time.sleep(0.1)
                    finally:
                        try: os.unlink(datei)
                        except Exception: pass
                    gesprochen = True
                except Exception as e:
                    print("Edge-TTS fallback (z.B. offline):", e)
            if not gesprochen and engine is not None:
                try:
                    engine.setProperty('rate', self.rate)
                    clean = re.sub(r'[^\w\säöüÄÖÜß.,!?\-:;() ]', '', text)
                    engine.say(clean); engine.runAndWait()
                except Exception as e: print("TTS:", e)
    def sprich(self, t):
        """Alles vorlesen: Text in Stücke teilen und komplett einreihen."""
        if self.stumm: return  # STUMM = absolute Stille, keine Ausnahme
        if not self.enabled or not t: return
        if not (EDGE_OK or TTS_AVAILABLE): return
        clean = str(t).strip()
        if not clean: return
        Teile, cur = [], ""
        for satz in re.split(r'(?<=[.!?])\s+', clean):
            if len(cur) + len(satz) + 1 <= self.CHUNK:
                cur = (cur + " " + satz).strip()
            else:
                if cur: Teile.append(cur)
                while len(satz) > self.CHUNK:
                    Teile.append(satz[:self.CHUNK]); satz = satz[self.CHUNK:]
                cur = satz
        if cur: Teile.append(cur)
        for teil in Teile:
            if self.q.qsize() > 30:
                try: self.q.get_nowait()
                except queue.Empty: pass
            self.q.put(teil)
    def halt(self):
        """Sofort still sein: Warteschlange leeren + laufende Ansage stoppen."""
        while not self.q.empty():
            try: self.q.get_nowait()
            except queue.Empty: break
        try:
            if self._mixer_ok: _pygame.mixer.music.stop()
        except Exception: pass
        try:
            if self.engine: self.engine.stop()
        except Exception: pass
    def stop(self): self.aktiv = False

# ---------- Computer: sehen (Screenshot + Vision) + Maus ----------
try:
    from PIL import ImageGrab
    PIL_OK = True
except ImportError:
    PIL_OK = False
try:
    import pyautogui as _pag
    _pag.FAILSAFE = True; _pag.PAUSE = 0.15
    PYAUTO_OK = True
except ImportError:
    PYAUTO_OK = False

SHOTS = WORKSPACE / "quassel-ki" / "shots"
try: SHOTS.mkdir(parents=True, exist_ok=True)
except Exception: pass
VISION_MODEL = os.environ.get("QUASSEL_VISION", "moondream")

def screenshot_machen(maxbreite=1280):
    if not PIL_OK: return None, "Pillow fehlt: pip install pillow"
    try:
        img = ImageGrab.grab()
        img.thumbnail((maxbreite, maxbreite))
        pf = SHOTS / f"shot_{datetime.now():%Y%m%d_%H%M%S}.png"
        img.save(pf)
        try:  # Optimierung: nur letzte 20 Shots behalten
            shots = sorted(SHOTS.glob("shot_*.png"))
            for alt in shots[:-20]: alt.unlink()
        except Exception: pass
        return pf, None
    except Exception as e:
        return None, str(e)

def agent_shot(breite=1280):
    """Screenshot exakt `breite` px breit für den Live-Agenten. Gibt (pfad, skalierung, fehler)."""
    if not PIL_OK: return None, 1.0, "Pillow fehlt: pip install pillow"
    try:
        from PIL import Image
        img = ImageGrab.grab()
        w0, h0 = img.size
        sk = w0 / float(breite)
        img = img.resize((breite, int(h0 / sk)), Image.LANCZOS)
        pf = SHOTS / f"agent_{datetime.now():%Y%m%d_%H%M%S}.png"
        img.save(pf)
        return pf, sk, None
    except Exception as e:
        return None, 1.0, str(e)

def bild_sehen(frage, bildpfad, timeout=180):
    data = base64.b64encode(Path(bildpfad).read_bytes()).decode()
    payload = json.dumps({"model": VISION_MODEL, "prompt": frage, "stream": False,
                          "options": {"num_predict": 200}, "images": [data]}).encode()
    req = urllib.request.Request("http://127.0.0.1:11434/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "(leer)")

# ---------- GPT-Features: Memory, Anhänge, Projekt-Index ----------
MEMORY_PFAD = WORKSPACE / "quassel-ki" / "memory.json"
INDEX_PFAD = WORKSPACE / "quassel-ki" / "projekt_index.json"

def memory_laden():
    try:
        if MEMORY_PFAD.exists():
            return json.loads(MEMORY_PFAD.read_text(encoding="utf-8"))
    except Exception: pass
    return {"fakten": []}

def memory_hinzu(fakt):
    mem = memory_laden()
    fakt = str(fakt).strip()[:300]
    if fakt and fakt not in mem["fakten"]:
        mem["fakten"].append(fakt)
        mem["fakten"] = mem["fakten"][-40:]
        MEMORY_PFAD.write_text(json.dumps(mem, ensure_ascii=False, indent=2), encoding="utf-8")
    return mem

def memory_text():
    # v20-Phase3: EIN System – memory2.json ist die Wahrheit, legacy wird mitgelesen
    try:
        if _HAT_QUASSEL_PAKET:
            daten = MEM2.laden(str(MEMORY2_PFAD))["eintraege"]
            lebendig = [e for e in daten if not MEM2.abgelaufen(e)]
            if lebendig:
                return MEM2.als_systemtext(lebendig[-20:])
    except Exception: pass
    fakten = memory_laden().get("fakten", [])
    return "" if not fakten else "Gemerkte Fakten über Nutzer/Projekte:\n- " + "\n- ".join(fakten)

def datei_text_lesen(pfad, limit=12000):
    p = Path(str(pfad))
    if p.stat().st_size > 200000: return None, "Datei zu groß (>200KB)."
    try: return p.read_text(encoding="utf-8", errors="replace")[:limit], None
    except Exception as e: return None, str(e)

def projekt_index_bauen(ordner, max_dateien=400):
    exts = {".h", ".cpp", ".cs", ".ini", ".uproject", ".py", ".json"}
    treffer = []
    for f in Path(ordner).rglob("*"):
        if len(treffer) >= max_dateien: break
        try:
            if f.is_file() and f.suffix.lower() in exts and "Intermediate" not in str(f) and "Saved" not in str(f):
                treffer.append({"pfad": str(f), "bytes": f.stat().st_size})
        except Exception: continue
    INDEX_PFAD.write_text(json.dumps({"ordner": str(ordner), "dateien": treffer}, ensure_ascii=False, indent=2), encoding="utf-8")
    return treffer

# ---------- Ollama Live-Chat ----------
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = os.environ.get("QUASSEL_MODEL", "quassel-ki")
# v17: Modell im Speicher halten (spart 30-60s Nachladen pro Antwort) + Fenster passend halten
KEEP_ALIVE = os.environ.get("QUASSEL_KEEP_ALIVE", "30m")
NUM_CTX = int(os.environ.get("QUASSEL_NUM_CTX", "8192"))
NUM_GPU = int(os.environ.get("QUASSEL_NUM_GPU", "0"))  # 0 = Ollama entscheidet (teilt VRAM/RAM selbst)
# Stabiler Prefix für den Prompt-Cache: Systemprompt + Skills immer byte-gleich am Anfang
_PREFIX_CACHE = {}

def ollama_server_ok(timeout=3):
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def ollama_stream(messages, out_q, fertig, modell=None, num_ctx=None):
    """Fragt das Modell im Stream. Tokens -> out_q (str), am Ende fertig.set(). Fehler -> out_q.put('[FEHLER]...')."""
    try:
        budget = int(globals().get("CHAT_TOKENS", os.environ.get("QUASSEL_CHAT_TOKENS", "400")))  # Chat kurz+flott, Schmiede nutzt vollen Default
        opts = {"num_predict": budget, "num_ctx": int(num_ctx or NUM_CTX)}
        if NUM_GPU: opts["num_gpu"] = NUM_GPU
        payload = {"model": modell or OLLAMA_MODEL, "messages": messages, "stream": True,
                   "keep_alive": KEEP_ALIVE, "options": opts}
        req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            for raw in r:
                if not raw.strip(): continue
                try: obj = json.loads(raw.decode())
                except Exception: continue
                if "error" in obj:
                    out_q.put(f"\n[Modell-Fehler: {obj['error']}]"); break
                tok = obj.get("message", {}).get("content", "")
                if tok: out_q.put(tok)
                if obj.get("done"): break
    except Exception as e:
        out_q.put(f"\n[Verbindung zu Ollama fehlgeschlagen: {e} -> Offline-Modus]")
    finally:
        fertig.set()

def ollama_chat_once(messages, modell=None, timeout=300, tokens=None):
    """Einmalige Antwort ohne Stream (für Agent + Reviews)."""
    opts = {"num_ctx": NUM_CTX}
    if tokens: opts["num_predict"] = tokens
    if NUM_GPU: opts["num_gpu"] = NUM_GPU
    payload = {"model": modell or OLLAMA_MODEL, "messages": messages, "stream": False,
               "keep_alive": KEEP_ALIVE, "options": opts}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        o = json.loads(r.read().decode())
        return o.get("message", {}).get("content", "")  # /api/chat -> message.content (NICHT response!)

AGENT_MODEL = os.environ.get("QUASSEL_AGENT", "llama3.1")  # schnell+klein für Live-Schritte
AGENT_TOOLS = ("datei_lesen(datei), ordner_auflisten(ordner), projekt_suchen(), projekt_index(ordner), "
    "datei_schreiben(datei, inhalt), text_ersetzen(datei, alt, neu), code_ausfuehren(datei), "
    "actor_erstellen_tool(ordner, klasse), ue_plugin_installieren(projekt, name), "
    "git_status(ordner), git_diff(ordner, datei), git_commit(ordner, nachricht), doku_suchen(thema), "
    "projekt_geruest(projekt_ordner, spielname), klassen_batch(ordner, klassen), asset_struktur(projekt_ordner), "
    "tasks_status(spiel), task_check(spiel, nr), tasks_json_schreiben(spiel, tasks), git_branch(ordner, name), cpp_check(datei), "
    "log_analyse(projekt_ordner), test_lauf(art, ziel), impact_check(ordner, klasse), doku_update(spiel, eintrag), "
    "bildschirm_foto(), bildschirm_sehen(frage), maus_position(), system_info(), tipp_ziehen()")
LESE_TOOLS = {"system_info", "projekt_suchen", "datei_lesen", "actor_vorschau", "tipp_ziehen",
              "bildschirm_foto", "bildschirm_sehen", "maus_position", "projekt_index", "ordner_auflisten",
              "git_status", "git_diff", "doku_suchen", "tasks_status", "git_branches",
              "cpp_check", "log_analyse", "impact_check"}
LIVE_SYS = ("Du steuerst den PC des Nutzers im Live-Modus (ausdrücklich genehmigt). "
    "Du bekommst pro Runde: Aufgabe, Bildschirmbeschreibung (Bild ist 1280px breit), Mausposition. "
    "Antworte mit GENAU EINEM Aktionsblock:\n```action\n{\"tool\": \"click\", \"x\": 800, \"y\": 450}\n```\n"
    "Tools: click(x,y im 1280er-Bild), type(text), key(name wie enter, tab, esc), wait(sekunden 1-5), "
    "say(kurze Meldung an Nutzer), done(Ergebnis-Zusammenfassung). "
    "Ohne Aktionsblock = nur kurze Statusmeldung (max 2 Sätze). Genau 1 Aktion pro Antwort. "
    "Nie raten bei Passwörtern/Zahlungen: dann say + done. Antworte auf Deutsch.")

# ---------- v17: Erinnerung über Sessions hinweg ----------
_STOPW = {"der", "die", "das", "und", "oder", "ist", "war", "ich", "du", "er", "sie", "es", "mit", "von",
          "für", "auf", "in", "zu", "dem", "den", "der", "ein", "eine", "nicht", "aber", "wie", "was", "mach",
          "kann", "noch", "wir", "mir", "mich", "dich", "uns", "hat", "haben", "sind", "wird", "man"}

def _begriffe(text):
    return {w for w in re.findall(r"[a-zA-ZäöüÄÖÜß0-9_]{4,}", str(text).lower()) if w not in _STOPW}

def chat_erinnerung_suchen(frage, max_treffer=3, max_zeichen=1400):
    """Sucht in alten Chats nach dem, was zur Frage passt (einfaches BM25-artiges Scoring)."""
    try:
        q = _begriffe(frage)
        if not q: return ""
        treffer = []
        for f in sorted(CHATS_DIR.glob("*.json"), reverse=True)[:40]:
            try: obj = json.loads(f.read_text(encoding="utf-8"))
            except Exception: continue
            eintraege = obj.get("history", [])
            if not eintraege: continue
            punkte, sammel = 0, []
            for z in eintraege:
                if z.get("role") != "user": continue
                inhalt = str(z.get("content", ""))[:300]
                treffer_w = _begriffe(inhalt)
                s = len(q & treffer_w)
                if s:
                    punkte += s
                    sammel.append(inhalt)
            if punkte:
                treffer.append((punkte, f.stem, sammel))
        if not treffer: return ""
        treffer.sort(reverse=True)
        teile = []
        for punkte, name, sammel in treffer[:max_treffer]:
            teile.append(f"Aus früherem Chat ({name}): " + " | ".join(sammel[:3]))
        return ("\n".join(teile))[:max_zeichen]
    except Exception:
        return ""

def chat_erinnerung_speichern(frage, antwort):
    """Legt eine kompakte Erinnerung ab, damit themenübergreifend nicht alles vergessen wird."""
    try:
        f = WORKSPACE / "quassel-ki" / "erinnerungen.json"
        daten = json.loads(f.read_text(encoding="utf-8")) if f.exists() else []
        eintrag = {"frage": str(frage)[:300], "antwort": str(antwort)[:400], "zeit": datetime.now().isoformat(timespec="minutes")}
        daten.append(eintrag)
        f.write_text(json.dumps(daten[-120:], ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception: pass

# ---------- v18: quassel-Paket (Hardware, Router, Memory 2.0, Konfig) ----------
try:
    from quassel import hardware as HW, konfig as KONF, memory2 as MEM2, modelle as ROUTER, projekte as PROJ, schmiede as SCH, buildtest as BTEST, impact as IMP, auftrag as AUF
    _HAT_QUASSEL_PAKET = True
except Exception:
    HW = KONF = MEM2 = ROUTER = PROJ = SCH = BTEST = IMP = AUF = None
    _HAT_QUASSEL_PAKET = False
try:
    QCFG = KONF.laden(str(WORKSPACE / "quassel-ki" / "quassel.yaml")) if _HAT_QUASSEL_PAKET else {}
except Exception:
    QCFG = {}
# v20-Phase2: yaml-Werte gelten, Env überschreibt (QUASSEL_* hat Vorrang wenn gesetzt)
CHAT_TOKENS = 400
try:
    _ocfg, _ccfg = (QCFG.get("ollama", {}) or {}), (QCFG.get("chat", {}) or {})
    if "QUASSEL_KEEP_ALIVE" not in os.environ and _ocfg.get("keep_alive"):
        KEEP_ALIVE = str(_ocfg["keep_alive"])
    if "QUASSEL_NUM_CTX" not in os.environ and _ocfg.get("num_ctx"):
        NUM_CTX = int(_ocfg["num_ctx"])
    if "QUASSEL_CHAT_TOKENS" not in os.environ and _ccfg.get("tokens"):
        CHAT_TOKENS = int(_ccfg["tokens"])
    else:
        CHAT_TOKENS = int(os.environ.get("QUASSEL_CHAT_TOKENS", CHAT_TOKENS))
except Exception: pass
MEMORY2_PFAD = WORKSPACE / "quassel-ki" / "memory2.json"
SELF_CHECK_SCHEMA = {"type": "object", "properties": {
    "verstanden": {"type": "boolean"}, "etwas_erfunden": {"type": "boolean"},
    "dateien_ok": {"type": "boolean"}, "tests_ok": {"type": "boolean"},
    "restrisiken": {"type": "string"}, "confidence": {"type": "string"}},
    "required": ["verstanden", "confidence"]}
LESSON_SCHEMA = {"type": "object", "properties": {
    "aufgabe": {"type": "string"}, "vorgehen": {"type": "string"},
    "ergebnis": {"type": "string"}, "lesson": {"type": "string"}},
    "required": ["lesson"]}

# ---------- v17: Rolling-Summary-Kontext (statt hart abschneiden) ----------
CTX_LIMIT = int(os.environ.get("QUASSEL_CTX", "10"))
SUMMARY_PFAD = WORKSPACE / "quassel-ki" / "zusammenfassung.json"

def summary_laden():
    try:
        if SUMMARY_PFAD.exists():
            return json.loads(SUMMARY_PFAD.read_text(encoding="utf-8")).get("text", "")
    except Exception: pass
    return ""

def summary_speichern(text):
    try: SUMMARY_PFAD.write_text(json.dumps({"text": text, "stand": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
    except Exception: pass

def summary_bauen(alt, raus):
    """Fasst die ältesten Züge zusammen, damit wichtiges nicht verloren geht. Schnellmodell reicht."""
    try:
        transkript = "\n".join(f"{'Nutzer' if z.get('role') == 'user' else 'Quassel'}: {str(z.get('content',''))[:220]}" for z in raus)
        if len(transkript) < 80: return alt
        sys_alt = f"Bisheriger Stand:\n{alt}" if alt else "Noch kein früherer Stand."
        roh = ollama_chat_once([
            {"role": "system", "content": "Fasse das Gespräch als enges Gedächtnis-Protokoll zusammen. "
                "Behalte: Entscheidungen, Namen, Projekte, offene Aufgaben, Wünsche, Zahlen, Fehler. "
                "Weg: Höflichkeiten, Wiederholungen, Werkzeug-Details. "
                "Jeder Fakt genau EINMAL, keine Dopplungen, max 100 Wörter. Deutsch, Stichpunkte, kein Vorwort."},
            {"role": "user", "content": sys_alt + "\n\nNeue ältere Züge:\n" + transkript}],
            FAST_MODEL, 90, 260)
        neu = (roh or "").strip()
        return neu if len(neu) > 30 else alt
    except Exception:
        return alt

def verlauf_kuerzen(history, alt_summary=""):
    """Rolling Summary: letzte N Züge bleiben wörtlich, alles davor wird zur Zusammenfassung.
    Sicherheitsnetz: klappt das Zusammenfassen (Ollama aus), bleibt der Verlauf UNVERKÜRZT."""
    if len(history) <= CTX_LIMIT * 2: return history, alt_summary
    raus, bleiben = history[:-CTX_LIMIT], history[-CTX_LIMIT:]
    neu = summary_bauen(alt_summary, raus)
    if not neu:
        return history, alt_summary  # nichts verloren: nochmal versuchen beim nächsten Mal
    return bleiben, neu

# ---------- v16: Ton + Auto-Memory ----------
TONS = {
    "normal": "Ton normal: warm und natürlich wie ein guter Kumpel, der sich auskennt. Leichte Lockerheit ok, kein Klamauk.",
    "frech": "Ton frech: keck und vorlaut wie immer (Quassel-Original), aber nie verletzend.",
    "profi": "Ton profi: knapp, präzise, technisch. Keine Sprüche, direkt zur Sache.",
}

# ---------- v17: strukturierte Ausgabe (JSON-Schema statt Text-Raten) ----------
FAKTEN_SCHEMA = {
    "type": "object",
    "properties": {
        "fakten": {"type": "array", "items": {"type": "string"}},
        "aufgabe": {"type": "string"},
    },
    "required": ["fakten"],
}

def ollama_json(messages, schema, modell=None, timeout=120, tokens=200):
    """Strukturierte Antwort per JSON-Schema + temperature 0 -> kein Text-Raten mehr."""
    payload = {"model": modell or OLLAMA_MODEL, "messages": messages, "stream": False,
               "format": schema, "options": {"temperature": 0, "num_predict": tokens}}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        roh = json.loads(r.read().decode()).get("message", {}).get("content", "")
    return json.loads(roh)

def auto_fakten(verlauf_schnipsel):
    """Holt stabile Fakten (Name, Projekt, Vorlieben, Probleme) aus einem Austausch. Gibt Liste zurück."""
    try:
        obj = ollama_json([
            {"role": "system", "content": "Extrahiere stabile Fakten über den Nutzer: Name, Projekte, Vorlieben, Ziele, wiederkehrende Probleme. "
                "Nur bestätigte Fakten, keine Vermutungen, keine Höflichkeiten. Kein Fakt -> leere Liste."},
            {"role": "user", "content": verlauf_schnipsel[:1500]}], FAKTEN_SCHEMA, FAST_MODEL, 120, 200)
        fakten = [str(z).strip()[:200] for z in (obj.get("fakten") or []) if len(str(z).strip()) > 8]
        return fakten[:4], str(obj.get("aufgabe") or "")[:200]
    except Exception:
        try:
            roh = ollama_chat_once([
                {"role": "system", "content": "Extrahiere stabile Fakten über den Nutzer (Name, Projekte, Vorlieben, Ziele, Probleme). NUR Stichpunkten je Zeile mit '- ', oder 'keine'."},
                {"role": "user", "content": verlauf_schnipsel[:1500]}], FAST_MODEL, 120, 120)
            fakten = []
            for z in roh.splitlines():
                z = z.strip().lstrip("-•* ").strip()
                if len(z) > 8 and "keine" not in z.lower()[:10] and "?" not in z:
                    fakten.append(z[:200])
            return fakten[:4], ""
        except Exception:
            return [], ""

# ---------- v14: Router, Diff, Git, Web-Doku ----------
FAST_MODEL = "llama3.1"  # Sekunden statt Minuten
SCHWER_WOERTER = ("code", "klasse", "c++", "replikation", "replication", "blueprint", "niagara",
    "schreibe", "erstelle", "warum", "fehler", "bug", "crash", "plugin", "schmiede", "review",
    "commit", "funktion", "actor", "umg", "material", "multiplayer", "server", "git", "installer")

def route_modell(text, modus="auto", anhaenge_da=False):
    """auto: Kleinkram -> schnell, Schweres -> stark. Gibt (modellname, kuerzel) zurück."""
    if modus == "schnell": return FAST_MODEL, "⚡"
    if modus == "stark": return OLLAMA_MODEL, "🧠"
    t = (text or "").lower()
    schwer = anhaenge_da or len(text or "") > 220 or "```" in (text or "") or any(k in t for k in SCHWER_WOERTER)
    return (OLLAMA_MODEL, "🧠") if schwer else (FAST_MODEL, "⚡")

def diff_bauen(alt_text, neu_text, name="datei", max_zeilen=120):
    try:
        d = list(difflib.unified_diff(alt_text.splitlines(), neu_text.splitlines(),
                                      fromfile="alt/" + name, tofile="neu/" + name, lineterm=""))
        return "\n".join(d[:max_zeilen]) or "(kein Unterschied)"
    except Exception as e:
        return f"(Diff-Fehler: {e})"

def git_repo_suchen(start):
    p = Path(str(start or WORKSPACE)).resolve()
    for base in [p] + list(p.parents):
        if (base / ".git").exists(): return base
    return None

def git_laufen(args, cwd, timeout=20):
    r = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=timeout, cwd=str(cwd))
    return r.returncode, (r.stdout + r.stderr)[-4000:]

def doku_suchen(thema, max_zeichen=3500):
    """Live UE-Doku: bot-freundliche Suche + erste Epic/Docs-Seite als Auszug. Keine extra Pakete."""
    try:
        q = urllib.parse.quote(f"Unreal Engine 5 {thema} documentation")
        req = urllib.request.Request("https://lite.duckduckgo.com/lite/?q=" + q,
                                     headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            html = r.read().decode("utf-8", "replace")
        treffer = []
        for m in re.findall(r"//duckduckgo\.com/l/\?uddg=([^\"&]+)", html):
            url = urllib.parse.unquote(m)
            if url.startswith("http") and url not in treffer:
                treffer.append(url)
            if len(treffer) >= 6: break
        if not treffer:
            return "Keine Doku-Treffer (Suchbegriff anders formulieren)."
        epic = [u for u in treffer if "docs.unrealengine.com" in u or "dev.epicgames.com" in u]
        for url in (epic + [u for u in treffer if u not in epic])[:3]:
            try:
                req2 = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req2, timeout=20) as r2:
                    seite = r2.read().decode("utf-8", "replace")
                text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", seite, flags=re.S)
                text = re.sub(r"<[^>]+>", " ", text)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 500:
                    return f"Quelle: {url}\n" + text[:max_zeichen]
            except Exception:
                continue
        return "Treffer: " + "\n".join(treffer[:5]) + "\n(Seiten blockieren Abruf – Trefferliste oben.)"
    except Exception as e:
        return f"Doku-Suche geht nicht: {e}"

# ---------- v15: Forge (Unreal-Projekt aufbauen) ----------
ELTERN_KLASSEN = {
    "Actor": ("AActor", "GameFramework/Actor.h", "A"),
    "Pawn": ("APawn", "GameFramework/Pawn.h", "A"),
    "Character": ("ACharacter", "GameFramework/Character.h", "A"),
    "Component": ("UActorComponent", "Components/ActorComponent.h", "U"),
    "SceneComponent": ("USceneComponent", "Components/SceneComponent.h", "U"),
    "GameMode": ("AGameModeBase", "GameFramework/GameModeBase.h", "A"),
    "PlayerController": ("APlayerController", "GameFramework/PlayerController.h", "A"),
    "PlayerState": ("APlayerState", "GameFramework/PlayerState.h", "A"),
    "GameState": ("AGameStateBase", "GameFramework/GameStateBase.h", "A"),
    "SaveGame": ("USaveGame", "GameFramework/SaveGame.h", "U"),
    "Object": ("UObject", "UObject/NoExportTypes.h", "U"),
}

def forge_klasse_schreiben(ordner, name, eltern="Actor", member=()):
    basis, include, praefix = ELTERN_KLASSEN.get(eltern, ELTERN_KLASSEN["Actor"])
    roh = re.sub(r'\W', '', name) or "MyClass"
    klass = roh if roh.startswith(praefix) else praefix + roh  # UE: Dateiname == Klassenname
    props = ""
    for m in member[:8]:
        var = re.sub(r'\W', '', str(m)) or "Wert"
        props += f'\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category="{klass}")\n\tfloat {var} = 0.f;\n'
    h = (f'#pragma once\n#include "CoreMinimal.h"\n#include "{include}"\n#include "{klass}.generated.h"\n\n'
         f'UCLASS()\nclass {klass} : public {basis}\n{{\n\tGENERATED_BODY()\npublic:\n\t{klass}();\n{props}'
         f'protected:\n\tvirtual void BeginPlay() override;\n}};\n')
    cpp = (f'#include "{klass}.h"\n{klass}::{klass}()\n{{\n}}\n'
           f'void {klass}::BeginPlay()\n{{\n\tSuper::BeginPlay();\n\tUE_LOG(LogTemp, Warning, TEXT("{klass} bereit"));\n}}\n')
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{klass}.h").write_text(h, encoding="utf-8")
    (ordner / f"{klass}.cpp").write_text(cpp, encoding="utf-8")
    return klass

def tasks_lesen(spiel_ordner):
    t = Path(spiel_ordner) / "tasks.md"
    if not t.exists(): return None
    zeilen = t.read_text(encoding="utf-8", errors="replace").splitlines()
    offen, fertig = [], 0
    for i, z in enumerate(zeilen):
        s = z.strip()
        if s.startswith("- [ ]"): offen.append((i, s[5:].strip()))
        elif s.startswith("- [x]") or s.startswith("- [X]"): fertig += 1
    return {"pfad": t, "zeilen": zeilen, "offen": offen, "fertig": fertig}

# ---------- MCP-Werkzeuge (Model Context Protocol, minimal) ----------
# Eigene Tools laufen immer (ohne Server). Externe MCP-Server (stdio, z.B. per npx)
# können in mcp_config.json eingetragen werden. Jeder Schreib-/Server-Aufruf fragt nach.
MCP_CONFIG = WORKSPACE / "quassel-ki" / "mcp_config.json"
MCP_DEFAULT = {"servers": {"dateien-lokal (Beispiel, aus)": {
    "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", str(WORKSPACE)],
    "enabled": False}}}

class MCPClient:
    def __init__(self, log_fn):
        self.log_fn = log_fn
        self.procs = {}   # name -> Popen
        self.ids = {}
        self.tools_cache = {}
    def config_laden(self):
        try:
            if not MCP_CONFIG.exists():
                MCP_CONFIG.write_text(json.dumps(MCP_DEFAULT, indent=2), encoding="utf-8")
            return json.loads(MCP_CONFIG.read_text(encoding="utf-8"))
        except Exception as e:
            self.log_fn("Quassel-KI", f"MCP-Config Fehler: {e}")
            return {"servers": {}}
    def _send(self, name, methode, params=None, timeout=15):
        p = self.procs.get(name)
        if not p or p.poll() is not None: return {"_fehler": "Server läuft nicht"}
        self.ids[name] = self.ids.get(name, 0) + 1
        msg = {"jsonrpc": "2.0", "id": self.ids[name], "method": methode}
        if params is not None: msg["params"] = params
        try:
            p.stdin.write((json.dumps(msg) + "\n").encode()); p.stdin.flush()
            import select
            out = b""
            t0 = time.time()
            while time.time() - t0 < timeout:
                line = p.stdout.readline()
                if not line: break
                try: obj = json.loads(line.decode())
                except Exception: continue
                if obj.get("id") == self.ids[name]: return obj.get("result", obj)
            return {"_fehler": "Timeout"}
        except Exception as e:
            return {"_fehler": str(e)}
    def server_starten(self, name, cfg):
        try:
            p = subprocess.Popen([cfg["command"]] + cfg.get("args", []),
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.procs[name] = p
            self._send(name, "initialize", {"protocolVersion": "2024-11-05",
                      "capabilities": {}, "clientInfo": {"name": "quassel-ki", "version": "5"}})
            try: p.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n'); p.stdin.flush()
            except Exception: pass
            res = self._send(name, "tools/list")
            tools = res.get("tools", []) if isinstance(res, dict) else []
            self.tools_cache[name] = [t.get("name", "?") for t in tools]
            return True
        except Exception as e:
            self.log_fn("Quassel-KI", f"MCP-Server {name} startet nicht: {e}")
            return False
    def stoppen(self):
        for p in self.procs.values():
            try: p.terminate()
            except Exception: pass
        self.procs.clear()
    # --- eingebaute Werkzeuge (brauchen keinen Server) ---
    def builtin_tools(self):
        return ["system_info", "projekt_suchen", "datei_lesen", "actor_vorschau", "tipp_ziehen",
                "bildschirm_foto", "bildschirm_sehen", "maus_position",
                "projekt_index", "code_ausfuehren", "shell_befehl", "ue_plugin_installieren",
                "ordner_auflisten", "datei_schreiben", "text_ersetzen", "actor_erstellen_tool",
                "git_status", "git_diff", "git_commit", "doku_suchen",
                "projekt_geruest", "klassen_batch", "asset_struktur", "tasks_status", "task_check",
                "git_branch", "git_branches", "cpp_check", "log_analyse", "impact_check", "doku_update"]
    def alle_tools(self, plugintools=None):
        tools = [f"lokal/{t}" for t in self.builtin_tools()]
        for name, tl in self.tools_cache.items():
            tools += [f"{name}/{t}" for t in tl]
        for t in (plugintools or {}):
            tools.append(f"plugin/{t}")
        return tools
    def aufrufen(self, toolname, args, ctx):
        """ctx: dict mit pc(SafePC), sysinfo, projekt. Gibt Text zurück."""
        if "/" in toolname: server, tname = toolname.split("/", 1)
        else: server, tname = "lokal", toolname
        if server == "lokal":
            try:
                if tname == "system_info":
                    s = ctx["sysinfo"]
                    return f"Profil {s['profil']}, CPU-Kerne {s['cpu']}, RAM {s['ram']}GB, GPU {s['gpu']}, C: frei {s['disk_free']}GB, UE: {list(s['editors'].keys())}"
                if tname == "projekt_suchen":
                    projs = ctx["pc"].finde_projekte()
                    return "Keine .uproject gefunden." if not projs else "\n".join(str(p) for p in projs[:8])
                if tname == "datei_lesen":
                    pf = Path(str(args.get("pfad", "")))
                    if not ctx["pc"]._im_erlaubten_bereich(pf): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    if pf.stat().st_size > 200000: return "Datei zu groß (>200KB)."
                    return pf.read_text(encoding="utf-8", errors="replace")[:6000]
                if tname == "actor_vorschau":
                    name = re.sub(r'\W', '', str(args.get("name", "MyActor"))) or "MyActor"
                    return f"Vorschau: {name}.h/.cpp würden UCLASS-Actor mit MaxHP, BeginPlay+Tick erzeugen. Zum echten Erstellen: Button 'C++ Actor erstellen'."
                if tname == "tipp_ziehen":
                    return random.choice(UNREAL_TIPPS + CODING_TIPPS)
                if tname == "bildschirm_foto":
                    pf, err = screenshot_machen()
                    return f"Fehler: {err}" if err else f"Screenshot: {pf} (Vorschau im Chat-Fenster möglich)"
                if tname == "bildschirm_sehen":
                    pf, err = screenshot_machen()
                    if err: return f"Fehler: {err}"
                    try:
                        desc = bild_sehen("Describe this screenshot in detail: active windows, texts, buttons.", pf)
                        return f"Seheindruck (englisch, lass ihn dir per 'An Modell senden' auf Deutsch erklären):\n{desc}"
                    except Exception as e: return f"Vision-Modell ({VISION_MODEL}) nicht bereit: {e}"
                if tname == "maus_position":
                    if not PYAUTO_OK: return "pyautogui fehlt: pip install pyautogui"
                    x, y = _pag.position()
                    return f"Maus bei x={x}, y={y} (Bildschirm {_pag.size()})"
                if tname == "projekt_index":
                    basis = str(args.get("ordner") or (ctx.get("projekt").parent if ctx.get("projekt") else WORKSPACE))
                    zb = Path(basis)
                    if not zb.exists(): return f"Ordner fehlt: {basis}"
                    treffer = projekt_index_bauen(zb)
                    return f"Index: {len(treffer)} Dateien in {basis}.\n" + "\n".join(t['pfad'] for t in treffer[:40])
                if tname == "code_ausfuehren":
                    pf = Path(str(args.get("datei", "")))
                    if pf.suffix.lower() != ".py": return "Nur .py-Dateien."
                    if not ctx["pc"]._im_erlaubten_bereich(pf): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    ctx["pc"].aktion_loggen(f"code_ausfuehren {pf}")
                    try:
                        r = subprocess.run([sys.executable, str(pf)], capture_output=True, text=True, timeout=25)
                        out = (r.stdout + r.stderr)[-4000:]
                        return f"Exit {r.returncode}:\n{out or '(keine Ausgabe)'}"
                    except subprocess.TimeoutExpired:
                        return "Abgebrochen: Timeout (25s)."
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "ordner_auflisten":
                    zb = Path(str(args.get("ordner", "") or WORKSPACE))
                    if not ctx["pc"]._im_erlaubten_bereich(zb): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        alle = sorted(zb.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
                        gezeigt = alle[:200]
                        txt = "\n".join(("📄 " if p.is_file() else "📁 ") + p.name for p in gezeigt) or "(leer)"
                        if len(alle) > 200: txt += f"\n… +{len(alle) - 200} weitere (Namen eingrenzen!)"
                        return txt
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "datei_schreiben":
                    pf = Path(str(args.get("datei", "")))
                    inhalt = str(args.get("inhalt", ""))[:60000]
                    if not ctx["pc"]._im_erlaubten_bereich(pf): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        pf.parent.mkdir(parents=True, exist_ok=True)
                        neu = not pf.exists()
                        pf.write_text(inhalt, encoding="utf-8")
                        ctx["pc"].aktion_loggen(f"datei_schreiben {'neu' if neu else 'update'} {pf} ({len(inhalt)} Zeichen)")
                        return f"{'Erstellt' if neu else 'Überschrieben'}: {pf} ({len(inhalt)} Zeichen)"
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "text_ersetzen":
                    pf = Path(str(args.get("datei", "")))
                    alt, neu = str(args.get("alt", "")), str(args.get("neu", ""))
                    if not ctx["pc"]._im_erlaubten_bereich(pf): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        text = pf.read_text(encoding="utf-8")
                        if alt not in text: return "Stelle nicht gefunden (alt-Text fehlt exakt so in der Datei)."
                        n = text.count(alt)
                        pf.write_text(text.replace(alt, neu, 1 if args.get("einmal", True) else -1), encoding="utf-8")
                        ctx["pc"].aktion_loggen(f"text_ersetzen {pf} ({n}x gefunden)")
                        return f"Ersetzt ({n}x gefunden, {'erstes' if args.get('einmal', True) else 'alle'}): {pf}"
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "actor_erstellen_tool":
                    if not ctx.get("app"): return "App fehlt."
                    ORD = Path(str(args.get("ordner", "")))
                    KLA = re.sub(r'\W', '', str(args.get("klasse", "MyActor"))) or "MyActor"
                    if not ctx["pc"]._im_erlaubten_bereich(ORD): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        h, cpp = ctx["pc"].actor_erstellen(ORD, KLA)
                        ctx["pc"].aktion_loggen(f"actor_erstellen {KLA} in {ORD}")
                        return f"Erstellt: {h.name} + {cpp.name} in {ORD}"
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "git_status":
                    repo = git_repo_suchen(args.get("ordner") or ((ctx.get("projekt").parent if ctx.get("projekt") else None) or WORKSPACE))
                    if not repo: return "Kein Git-Repo gefunden."
                    code, out = git_laufen(["status", "--short"], repo)
                    return f"Repo: {repo}\n{(out.strip() or '(sauber)')[:2000]}"
                if tname == "git_diff":
                    repo = git_repo_suchen(args.get("ordner") or ((ctx.get("projekt").parent if ctx.get("projekt") else None) or WORKSPACE))
                    if not repo: return "Kein Git-Repo gefunden."
                    params = ["diff"]
                    if args.get("datei"): params += ["--", str(args.get("datei"))]
                    code, out = git_laufen(params, repo)
                    return (out.strip() or "(kein Diff)")[:4000]
                if tname == "git_commit":
                    repo = git_repo_suchen(args.get("ordner") or ((ctx.get("projekt").parent if ctx.get("projekt") else None) or WORKSPACE))
                    if not repo: return "Kein Git-Repo gefunden."
                    nachricht = str(args.get("nachricht", "")).strip()[:200]
                    if not nachricht: return "Keine Commit-Nachricht."
                    ctx["pc"].aktion_loggen(f"git_commit in {repo}: {nachricht}")
                    code, out = git_laufen(["commit", "-am", nachricht], repo)
                    return f"Exit {code}:\n{(out.strip() or '(ok)')[:1500]}"
                if tname == "doku_suchen":
                    thema = str(args.get("thema", "")).strip()
                    if not thema: return "Kein Thema."
                    return doku_suchen(thema)
                def _spiel_ordner():
                    s = str(args.get("spiel", "")).strip()
                    if not s: return None
                    p = Path(s)
                    ordner = p if p.exists() else (WORKSPACE / "quassel-ki" / "spiele" / re.sub(r'\W+', '', s)[:30])
                    return ordner if ctx["pc"]._im_erlaubten_bereich(ordner) else None
                if tname == "projekt_geruest":
                    basis = Path(str(args.get("projekt_ordner", "")))
                    spiel = re.sub(r'\W', '', str(args.get("spielname", "MeinSpiel"))) or "MeinSpiel"
                    engine = str(args.get("engine", "5.8"))
                    if not ctx["pc"]._im_erlaubten_bereich(basis): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        mod = spiel
                        (basis / f"{spiel}.uproject").write_text(json.dumps({
                            "FileVersion": 3, "EngineAssociation": "{" + engine + "}",
                            "Category": "", "Description": f"Mit Quassel-Forge erstellt.",
                            "Modules": [{"Name": mod, "Type": "Runtime", "LoadingPhase": "Default"}],
                            "Plugins": []}, indent=4), encoding="utf-8")
                        src = basis / "Source" / mod
                        src.mkdir(parents=True, exist_ok=True)
                        (src / f"{mod}.Target.cs").write_text(
                            f"using UnrealBuildTool;\npublic class {mod}Target : TargetRules\n{{\n"
                            f"\tpublic {mod}Target(TargetInfo Target) : base(Target)\n\t{{\n"
                            f"\t\tType = TargetType.Game;\n\t\tDefaultBuildSettings = BuildSettingsVersion.V5;\n"
                            f"\t\tExtraModuleNames.AddRange(new string[] {{ \"{mod}\" }});\n\t}}\n}}\n", encoding="utf-8")
                        (src / f"{mod}Editor.Target.cs").write_text(
                            f"using UnrealBuildTool;\npublic class {mod}EditorTarget : TargetRules\n{{\n"
                            f"\tpublic {mod}EditorTarget(TargetInfo Target) : base(Target)\n\t{{\n"
                            f"\t\tType = TargetType.Editor;\n\t\tDefaultBuildSettings = BuildSettingsVersion.V5;\n"
                            f"\t\tExtraModuleNames.AddRange(new string[] {{ \"{mod}\" }});\n\t}}\n}}\n", encoding="utf-8")
                        (basis / "Config").mkdir(exist_ok=True)
                        (basis / "Config" / "DefaultEngine.ini").write_text(
                            "[/Script/EngineSettings.GameMapsSettings]\nEditorStartupMap=/Game/Maps/Main.Main\n", encoding="utf-8")
                        ctx["pc"].aktion_loggen(f"projekt_geruest {spiel} in {basis}")
                        return (f"Gerüst '{spiel}' in {basis}: {spiel}.uproject (Engine {engine}), Source/{mod}/ (*.Target.cs), "
                                f"Config/, bereit für Content. In UE öffnen -> .sln generieren lassen.")
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "klassen_batch":
                    ORD = Path(str(args.get("ordner", "")))
                    raw = args.get("klassen", [])
                    try: klassen = json.loads(raw) if isinstance(raw, str) else raw
                    except Exception: return "klassen muss JSON-Liste sein: [{name, eltern, member[]}]"
                    if not ctx["pc"]._im_erlaubten_bereich(ORD): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    gemacht = []
                    try:
                        for k in klassen[:12]:
                            gemacht.append(forge_klasse_schreiben(ORD, k.get("name", "X"), k.get("eltern", "Actor"), k.get("member", [])))
                        ctx["pc"].aktion_loggen(f"klassen_batch {len(gemacht)} in {ORD}")
                        return "Erstellt: " + ", ".join(gemacht)
                    except Exception as e:
                        return f"Fehler nach {len(gemacht)} Klassen: {e}"
                if tname == "asset_struktur":
                    basis = Path(str(args.get("projekt_ordner", "")))
                    if not ctx["pc"]._im_erlaubten_bereich(basis): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        c = basis / "Content"
                        for d in ["Maps", "Blueprints/Player", "Blueprints/Enemies", "Blueprints/UI",
                                  "Materials", "Audio", "Niagara", "Data"]:
                            (c / d).mkdir(parents=True, exist_ok=True)
                        (c / "ASSETS.md").write_text(
                            "# Asset-Regeln\n- Prefixe: BP_, M_, MI_, S_, T_, A_, NS_, DT_\n"
                            "- Keine Leer-/Sonderzeichen, CamelCase.\n- Nie direkt in Content/ legen, immer Unterordner.\n"
                            "- Umbenennen nur per UE (Fix Up Redirectors danach).\n", encoding="utf-8")
                        ctx["pc"].aktion_loggen(f"asset_struktur in {basis}")
                        return f"Content-Struktur in {basis} angelegt (Maps, Blueprints/Player/Enemies/UI, Materials, Audio, Niagara, Data) + ASSETS.md."
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "tasks_status":
                    o = _spiel_ordner()
                    if not o: return "Spielordner unbekannt/außerhalb (spiel: Name oder Pfad)."
                    if _HAT_QUASSEL_PAKET and (o / "tasks.json").exists():
                        obj = SCH.lesen(str(o / "tasks.json"))
                        if obj: return SCH.status_text(obj)
                    t = tasks_lesen(o)
                    if not t: return "Keine tasks.md – erst Schmiede laufen lassen."
                    gesamt = len(t["offen"]) + t["fertig"]
                    zeilen = [f"{i+1}. {txt}" for i, txt in t["offen"][:10]]
                    return f"Fortschritt {t['fertig']}/{gesamt}:\nOffen:\n" + "\n".join(zeilen)
                if tname == "task_check":
                    o = _spiel_ordner()
                    if not o: return "Spielordner unbekannt/außerhalb."
                    ref = str(args.get("nr", args.get("id", ""))).strip().upper()
                    if _HAT_QUASSEL_PAKET and (o / "tasks.json").exists():
                        obj = SCH.lesen(str(o / "tasks.json"))
                        if not obj: return "tasks.json kaputt."
                        offene = [t for t in obj["tasks"] if t.get("status") != "fertig"]
                        ziel = None
                        for t in obj["tasks"]:
                            if t.get("id", "").upper() == ref:
                                ziel = t; break
                        if not ziel and ref.isdigit() and 1 <= int(ref) <= len(offene):
                            ziel = offene[int(ref) - 1]
                        if not ziel: return f"Task {ref} nicht gefunden (ID wie T001 oder Nummer)."
                        ziel["status"] = "fertig"
                        ok, fehler = SCH.schreiben(str(o / "tasks.json"), obj["tasks"], obj.get("spiel", ""), obj.get("idee", ""))
                        if not ok: return "Schreibfehler: " + "; ".join(fehler)
                        return f"Erledigt: {ziel['id']} {ziel.get('ziel','')[:80]}"
                    t = tasks_lesen(o)
                    if not t: return "Keine tasks.md."
                    try: nr = int(args.get("nr", 0))
                    except Exception: return "nr muss Zahl sein (Nummer aus tasks_status)."
                    if not (1 <= nr <= len(t["offen"])): return f"nr 1..{len(t['offen'])} wählen."
                    idx, txt = t["offen"][nr - 1]
                    zl = t["zeilen"]; zl[idx] = zl[idx].replace("- [ ]", "- [x]", 1)
                    t["pfad"].write_text("\n".join(zl), encoding="utf-8")
                    return f"Erledigt: {txt}"
                if tname == "tasks_json_schreiben":
                    o = _spiel_ordner()
                    if not o: return "Spielordner unbekannt/außerhalb (spiel: Name oder Pfad)."
                    if not _HAT_QUASSEL_PAKET: return "Schmiede-Modul fehlt."
                    roh = args.get("tasks", [])
                    if isinstance(roh, str):
                        try: roh = json.loads(roh)
                        except Exception: return "tasks muss Liste oder JSON-Liste sein."
                    if not isinstance(roh, list) or not roh: return "Keine Aufgaben übergeben."
                    gebaut = []
                    for i, r in enumerate(roh[:30], 1):
                        if isinstance(r, str): r = {"ziel": r}
                        if not isinstance(r, dict) or not str(r.get("ziel", "")).strip(): continue
                        gebaut.append(SCH.task_bauen(i, r.get("ziel"), r.get("akzeptanz"), r.get("dateien"),
                                                     r.get("systeme"), r.get("abhaengig_von"), r.get("risiko"),
                                                     r.get("testschritte"), r.get("status", "offen"), r.get("annahmen")))
                    ok, fehler = SCH.schreiben(str(o / "tasks.json"), gebaut, str(args.get("spiel") or ""), "")
                    if not ok: return "Validierung: " + "; ".join(fehler)
                    ctx["pc"].aktion_loggen(f"tasks_json in {o}: {len(gebaut)} Tasks")
                    return f"tasks.json: {len(gebaut)} strukturierte Aufgaben in {o}."
                if tname in ("git_branch", "git_branches"):
                    repo = git_repo_suchen(args.get("ordner") or ((ctx.get("projekt").parent if ctx.get("projekt") else None) or WORKSPACE))
                    if not repo: return "Kein Git-Repo gefunden."
                    if tname == "git_branches":
                        code, out = git_laufen(["branch", "--list"], repo)
                        return (out.strip() or "(keine)")[:1500]
                    name = re.sub(r'[^\w\-/]', '', str(args.get("name", "")))[:60]
                    if not name: return "Branch-Name fehlt."
                    code, out = git_laufen(["checkout", "-b", name], repo)
                    if code != 0:
                        code, out = git_laufen(["checkout", name], repo)
                    ctx["pc"].aktion_loggen(f"git_branch {name} in {repo}")
                    return f"Exit {code}:\n{(out.strip() or '(ok)')[:800]}"
                if tname == "cpp_check":
                    pf = Path(str(args.get("datei", "")))
                    if not ctx["pc"]._im_erlaubten_bereich(pf): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try: text = pf.read_text(encoding="utf-8", errors="replace")
                    except Exception as e: return f"Fehler: {e}"
                    befunde = []
                    ist_header = pf.suffix.lower() == ".h"
                    if ist_header:
                        if "GENERATED_BODY()" not in text: befunde.append("❌ GENERATED_BODY() fehlt")
                        if ".generated.h" not in text: befunde.append("❌ #include *.generated.h fehlt")
                        if "#pragma once" not in text: befunde.append("⚠️ #pragma once fehlt")
                    if re.search(r"::BeginPlay\(\)\s*\{", text) and "Super::BeginPlay()" not in text: befunde.append("❌ Super::BeginPlay() fehlt")
                    if re.search(r"::Tick\s*\(.*\)\s*\{", text) and "Super::Tick" not in text: befunde.append("❌ Super::Tick fehlt")
                    if re.search(r"\bdelete\b", text): befunde.append("⚠️ rohes delete (in UE meist falsch – GC/UPROPERTY prüfen)")
                    if "UPROPERTY()" in text and "UPROPERTY(Edit" not in text and "UPROPERTY(Blueprint" not in text and "UPROPERTY(Replicated" not in text:
                        befunde.append("ℹ️ nacktes UPROPERTY() – ok für GC-Schutz, für Editor EditAnywhere/BlueprintReadWrite nötig")
                    return ("✅ sauber (statisch)" if not befunde else "\n".join(befunde)) + f"\nGeprüft: {pf.name} ({len(text)} Zeichen)"
                if tname == "log_analyse":
                    basis = Path(str(args.get("projekt_ordner", "") or (ctx.get("projekt").parent if ctx.get("projekt") else "")))
                    logs = sorted((basis / "Saved" / "Logs").glob("*.log")) if basis else []
                    if not logs: return "Keine Logs (Saved/Logs fehlt – schon mal in UE gespielt?)."
                    try:
                        roh = logs[-1].read_text(encoding="utf-8", errors="replace")
                        text = roh.splitlines()
                        treffer = [z.strip()[:220] for z in text if re.search(r"Error|Fatal|Exception|Access violation|Ensure|Failed", z)]
                        aus = treffer[-25:] or ["(keine Fehler im Log – läuft!)"]
                        erg = f"Log: {logs[-1].name}\n" + "\n".join(aus)
                        if _HAT_QUASSEL_PAKET:  # Phase 6: konkrete nächste Schritte statt nur Text
                            a = BTEST.analysieren(roh[-30000:])
                            erg += f"\nUrsache (Heuristik): {a['ursache']}\nNächste Schritte:\n" + "\n".join(f"→ {s}" for s in a["schritte"])
                        else:
                            erg += "\nTipp: Bei Crash 'crash-debug'-Skill fragen."
                        return erg
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "test_lauf":
                    # Phase 6: Build/Test-Adapter. Ausführung fragt über Permit (nicht in LESE_TOOLS).
                    if not _HAT_QUASSEL_PAKET: return "Build-Modul fehlt."
                    art = str(args.get("art", "python_test"))
                    ziel = str(args.get("ziel", ""))
                    zb = Path(ziel) if ziel else WORKSPACE
                    if not ctx["pc"]._im_erlaubten_bereich(zb): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    try:
                        erg = BTEST.lauf(art, ziel or str(zb), cwd=str(zb if zb.is_dir() else zb.parent),
                                         timeout=int(args.get("timeout", 300) or 300),
                                         log_ordner=str(WORKSPACE / "quassel-ki" / "logs"))
                    except Exception as e:
                        return f"Fehler: {e}"
                    ctx["pc"].aktion_loggen(f"test_lauf {art} {ziel} -> {'OK' if erg.get('ok') else 'FEHLER'}")
                    return BTEST.bericht(erg)[:4000]
                if tname == "impact_check":
                    ORD = Path(str(args.get("ordner", "")))
                    klasse = re.sub(r'\W', '', str(args.get("klasse", "")))
                    if not klasse: return "Klasse fehlt."
                    if not ctx["pc"]._im_erlaubten_bereich(ORD): return "Pfad außerhalb der erlaubten Ordner – abgelehnt."
                    if _HAT_QUASSEL_PAKET:
                        a = IMP.analysieren(str(ORD), klasse)
                        if a.get("fehler"): return a["fehler"]
                        return IMP.bericht(a)
                    treffer = []
                    try:
                        for f in ORD.rglob("*"):
                            if f.suffix.lower() not in (".h", ".cpp", ".cs", ".ini") or "Intermediate" in str(f): continue
                            try:
                                if klasse in f.read_text(encoding="utf-8", errors="replace") and f.stem != klasse:
                                    treffer.append(str(f.relative_to(ORD)) if str(f).startswith(str(ORD)) else f.name)
                            except Exception: continue
                            if len(treffer) >= 30: break
                    except Exception as e:
                        return f"Fehler: {e}"
                    risiko = "niedrig" if len(treffer) < 3 else ("mittel" if len(treffer) < 10 else "HOCH")
                    return (f"Impact {klasse}: {len(treffer)} Nutzer (Risiko {risiko})\n" + "\n".join(treffer[:30])) or f"Impact {klasse}: keine Nutzer gefunden (sicher umzubauen)."
                if tname == "doku_update":
                    o = _spiel_ordner()
                    if not o: return "Spielordner unbekannt/außerhalb."
                    eintrag = str(args.get("eintrag", "")).strip()[:800]
                    if not eintrag: return "Eintrag fehlt."
                    try:
                        with open(o / "DOKU.md", "a", encoding="utf-8") as f:
                            f.write(f"\n## {datetime.now():%Y-%m-%d %H:%M}\n{eintrag}\n")
                        return "DOKU.md aktualisiert."
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "shell_befehl":
                    if not ctx["pc"].unbegrenzt: return "Nur im Alles-Modus (🔓) verfügbar."
                    cmd = str(args.get("befehl", ""))[:500]
                    for pat in SHELL_BLOCKLISTE:
                        if re.search(pat, cmd, re.IGNORECASE):
                            ctx["pc"].aktion_loggen(f"shell BLOCKIERT: {cmd}")
                            return f"Blockiert (Sicherheitsliste): {pat}"
                    ctx["pc"].aktion_loggen(f"shell: {cmd}")
                    try:
                        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=str(WORKSPACE))
                        return f"Exit {r.returncode}:\n{(r.stdout + r.stderr)[-4000:] or '(keine Ausgabe)'}"
                    except subprocess.TimeoutExpired:
                        return "Abgebrochen: Timeout (30s)."
                    except Exception as e:
                        return f"Fehler: {e}"
                if tname == "ue_plugin_installieren":
                    return ctx.get("app").ue_plugin_installieren(str(args.get("projekt", "")), str(args.get("name", "MeinPlugin")), _mit_nachfrage=False) if ctx.get("app") else "App fehlt."
                plugintools = ctx.get("plugintools", {})
                if tname in plugintools:
                    try: return str(plugintools[tname](args, ctx))[:6000]
                    except Exception as e: return f"Plugin-Fehler: {e}"
                return "Unbekanntes lokales Tool."
            except Exception as e:
                return f"Fehler: {e}"
        if server == "plugin":
            plugintools = ctx.get("plugintools", {})
            if tname in plugintools:
                try: return str(plugintools[tname](args, ctx))[:6000]
                except Exception as e: return f"Plugin-Fehler: {e}"
            return "Plugin-Tool unbekannt (Plugin deaktiviert?)."
        res = self._send(server, "tools/call", {"name": tname, "arguments": args})
        try: return json.dumps(res, ensure_ascii=False)[:6000]
        except Exception: return str(res)[:6000]

# ---------- System-Check ----------
def get_ram_gb():
    try:
        import ctypes
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        s = MS(); s.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s))
        return round(s.ullTotalPhys / (1024**3), 1)
    except Exception: return 0

def get_gpu():
    try:
        out = subprocess.check_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                                      text=True, timeout=5)
        return out.strip().split("\n")[0]
    except Exception:
        return "NVIDIA RTX A1000 6GB (bekannt vom Vor-Check)"

def find_unreal_editors():
    found = {}
    for ver, p in [("5.8", r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"),
                   ("5.6", r"C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe")]:
        if os.path.exists(p): found[ver] = p
    return found

def system_check():
    cpu = os.cpu_count()
    ram = get_ram_gb() or 63.7
    disk_free = round(shutil.disk_usage("C:\\").free / (1024**3), 1)
    gpu = get_gpu()
    editors = find_unreal_editors()
    # Profil: deine Kiste: CPU stark, RAM riesig, GPU mittel, Disk knapp
    if ram >= 32 and cpu >= 12 and "A1000" in gpu:
        profil = "MEDIUM-HIGH"
        empf = ("Dein PC: i7-13700H + 64GB RAM = top fuer Compiles. "
                "Aber RTX A1000 6GB + nur {:.0f}GB frei auf C: -> Unreal auf Mittel stellen: "
                "Lumen auf Medium, Nanite ok, keine 4K-Lightmaps, regelmaessig DerivedDataCache leeren.").format(disk_free)
        einstellungen = {"bock": 70, "stille": 25, "tts_an": True, "scalability": "Medium"}
    elif ram < 16:
        profil = "LOW"; empf = "Wenig RAM – Unreal auf Low, TTS aus, wenig Tabs."; einstellungen = {"bock": 40, "stille": 45, "tts_an": False, "scalability": "Low"}
    else:
        profil = "MEDIUM"; empf = "Solide Mitte – Unreal Medium."; einstellungen = {"bock": 60, "stille": 30, "tts_an": True, "scalability": "Medium"}
    if disk_free < 50:
        empf += " ! Platte knapp! Mach Platz, Unreal-Projekte fressen 20-50GB."
    return {"cpu": cpu, "ram": ram, "gpu": gpu, "disk_free": disk_free,
            "editors": editors, "profil": profil, "empfehlung": empf, "preset": einstellungen}

# ---------- Sicherer PC-Zugriff (+ Alles-Modus mit Blockliste) ----------
SHELL_BLOCKLISTE = [r"format\s+[a-z]:", r"mkfs", r"rd\s+/s.*c:\\windows", r"del\s+.*system32",
    r"reg\s+delete\s+HKLM", r"shutdown\s+/s", r"diskpart", r":\(\)\{\s*:\|\:&\s*\};:",
    r"rm\s+-rf\s+/( |$)", r"dd\s+if=", r"cipher\s+/w:c", r"takeown.*c:\\windows"]

class SafePC:
    def __init__(self, log_fn):
        self.log_fn = log_fn
        self.darf = False  # Checkbox in UI
        self.unbegrenzt = False  # Alles-Modus (nur nach ALLES-Bestätigung)
    def _im_erlaubten_bereich(self, pfad: Path):
        try:
            rp = pfad.resolve()
            if self.unbegrenzt:
                # Alles-Modus: überall außer Windows-/System-Ordnern beim SCHREIBEN
                sysordner = [Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve(),
                             Path(r"C:\Windows\System32").resolve()]
                if any(str(rp).lower().startswith(str(s).lower()) for s in sysordner):
                    return False
                return True
            return any(str(rp).lower().startswith(str(r.resolve()).lower()) for r in ALLOWED_ROOTS if r.exists() or r == WORKSPACE)
        except Exception: return False
    def aktion_loggen(self, text):
        try:
            with open(WORKSPACE / "quassel-ki" / "aktionen.log", "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {text}\n")
        except Exception: pass
    def finde_projekte(self, max_treffer=10):
        treffer = []
        suchorte = [p for p in ALLOWED_ROOTS if p.exists()] + [Path.home() / "Documents"]
        gesehen = set()
        for ort in suchorte:
            try:
                for f in ort.rglob("*.uproject"):
                    if str(f) in gesehen: continue
                    gesehen.add(str(f))
                    treffer.append(f)
                    if len(treffer) >= max_treffer: return treffer
            except Exception: continue
        return treffer
    def lese_uproject(self, pfad: Path):
        try: return json.loads(pfad.read_text(encoding="utf-8"))
        except Exception as e: return {"_fehler": str(e)}
    def actor_erstellen(self, ordner: Path, classname: str):
        """Erstellt MyActor.h/.cpp Template. Fragt vorher per UI nach."""
        classname = re.sub(r'\W', '', classname) or "MyActor"
        if not classname[0].isupper(): classname = classname.capitalize()
        h = ordner / f"{classname}.h"
        cpp = ordner / f"{classname}.cpp"
        h_text = f"""#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "{classname}.generated.h"

UCLASS()
class A{classname} : public AActor
{{
    GENERATED_BODY()
public:
    A{classname}();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Health")
    float MaxHP = 100.f;
protected:
    virtual void BeginPlay() override;
public:
    virtual void Tick(float DeltaTime) override;
}};
"""
        cpp_text = f"""#include "{classname}.h"
A{classname}::A{classname}()
{{
    PrimaryActorTick.bCanEverTick = true;
}}
void A{classname}::BeginPlay()
{{
    Super::BeginPlay();
    UE_LOG(LogTemp, Warning, TEXT("{classname} ready! HP=%f"), MaxHP);
}}
void A{classname}::Tick(float DeltaTime)
{{
    Super::Tick(DeltaTime);
}}
"""
        h.write_text(h_text, encoding="utf-8"); cpp.write_text(cpp_text, encoding="utf-8")
        return h, cpp
    def projekt_starten(self, uproject: Path, editor_exe: str):
        return subprocess.Popen([editor_exe, str(uproject)])

# ---------- Wissen (kompakt aus v2) ----------
UNREAL_TIPPS = [
    "Unreal-Tipp: BeginPlay für Setup, Tick nur wenn nötig – Tick frisst Performance!",
    "Unreal-Tipp: UPROPERTY(EditAnywhere, BlueprintReadWrite) macht C++ Variablen im Editor sichtbar.",
    "Unreal-Tipp: Enhanced Input ab UE 5.1 – altes Input Mapping ist deprecated.",
    "Unreal-Tipp: Replication: nie Tick replizieren, nur Änderungen. Sonst Lag.",
    "Unreal-Tipp: Bei deiner A1000 6GB: Lumen auf Medium, Schatten-Mittel, kein 4K.",
]
CODING_TIPPS = [
    "Coding-Tipp: Kleine Funktionen, max 30 Zeilen, ein Job pro Funktion.",
    "Coding-Tipp: UE_LOG(LogTemp, Warning, TEXT(\"x=%f\"), X) statt raten.",
    "Coding-Tipp: Smart Pointer statt new/delete. In Unreal: UPROPERTY damit GC dich kennt.",
]
WISSEN = {
    "blueprint": "Blueprints = visuelles Scripting. Prototyp ja, Performance-kritisch lieber C++. Funktionen statt Copy-Paste.",
    "actor": "AActor = Basis für Welt-Objekte. Pawn = kontrollierbar, Character = Pawn mit Movement. Spawnen mit SpawnActor.",
    "tick": "Tick läuft jedes Frame. PrimaryActorTick.bCanEverTick = true + Tick(DeltaTime) überschreiben. So selten wie möglich!",
    "beginplay": "BeginPlay einmal beim Start. Super::BeginPlay() nicht vergessen!",
    "uproperty": 'UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Health") float MaxHP = 100.f;',
    "replication": "UPROPERTY(Replicated) + GetLifetimeReplicatedProps + DOREPLIFETIME. RPCs: UFUNCTION(Server/Client/NetMulticast).",
    "lumen": "Lumen = dynamisches Licht ohne Backen. Bei deiner A1000 auf Medium lassen.",
    "nanite": "Nanite = High-Poly ohne LODs, nur Static Meshes.",
    "git": "git status / add / commit -m / push. Features in Branches.",
    "c++": "In Unreal: TArray statt vector, FString statt string, kein delete auf UObject!",
    "pointer": "Nie delete auf UObject – GC macht das. UPROPERTY() setzen sonst Crash.",
    "performance": "Bei dir: 64GB RAM top, GPU mittel. Scalability Medium, Lumen Medium, DerivedDataCache leeren wenn Platte voll.",
}
def finde_wissen(f):
    q = " " + f.lower() + " "
    for k, v in WISSEN.items():
        if k in q: return v
    return None

# ---------- Codex-Theme (dark) + Sessions ----------
THEME = {
    "bg": "#0d1117", "panel": "#161b22", "panel2": "#1c2128",
    "fg": "#e6edf3", "muted": "#8b949e", "accent": "#2f81f7",
    "green": "#3fb950", "orange": "#d29922", "red": "#f85149",
    "du": "#79c0ff", "ki": "#e6edf3", "sys": "#8b949e",
    "code_bg": "#1c2128", "code_fg": "#a5d6ff",
}
CHATS_DIR = WORKSPACE / "quassel-ki" / "chats"
try: CHATS_DIR.mkdir(parents=True, exist_ok=True)
except Exception: pass

BEFEHLE = {
    "/help": "Befehle: /neu /clear /still /laut /leise /shot /sehen /maus /memory /index /tipp /modell /ctx /skill /plugin /god /export /permit /status /review /schmiede /mode /commit /geruest /tasks /logcheck /impact /ton /verlauf /speed /stumm /quasseln /agentstop /stopalles /scan /finish",
    "/neu": None, "/clear": None, "/still": None, "/laut": None, "/leise": None,
    "/shot": None, "/sehen": None, "/maus": None, "/memory": None,
    "/index": None, "/tipp": None, "/modell": None, "/ctx": None,
    "/skill": None, "/plugin": None, "/god": None, "/export": None,
    "/permit": "Lesen|Auto|Voll – /permit voll schaltet Alles-Modus (mit ALLES-Code)",
    "/status": "Status: Modell, Kontext, Modus, Stimme, Live",
    "/review": "Code-Review: erst Datei per 📎 oder @Name anhängen, dann /review",
    "/schmiede": "Spiel-Schmiede: aus Idee werden GDD.md + tasks.md + klassen.md",
    "/mode": "Modus: /mode ask (nur reden) | /mode agent (arbeitet)",
    "/commit": "Git: Status zeigen, Message vorschlagen, committen",
    "/geruest": "Unreal-Gerüst bauen (.uproject + Source + Config)",
    "/tasks": "Tasks-Status: /tasks Spielname",
    "/logcheck": "Unreal-Log analysieren (letzte Fehler)",
    "/impact": "Impact: /impact KlassenName (wer nutzt sie?)",
    "/ton": "Ton: /ton normal|frech|profi",
    "/verlauf": "Gedächtnis zeigen (Zusammenfassung langer Chats)",
    "/speed": "Speed: /speed FAST|BALANCED|SMART|MAXIMUM",
    "/stumm": "Stumm an/aus (arbeitet weiter, spricht nicht)",
    "/quasseln": "Quasseln-Stop an/aus (nur spontanes Reden)",
    "/agentstop": "Agent sauber anhalten",
    "/stopalles": "Globaler Not-Aus",
    "/scan": "Projekte scannen + Aufgaben finden (/scan Pfad)",
    "/finish": "Find&Finish an/aus (autonom sichere Tasks abarbeiten)",
}

# ---------- Skills + Plugins ----------
SKILLS_DIR = WORKSPACE / "quassel-ki" / "skills"
PLUGINS_DIR = WORKSPACE / "quassel-ki" / "plugins"

def skills_laden():
    skills = []
    try:
        for f in sorted(SKILLS_DIR.glob("*.json")):
            try: skills.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception: continue
    except Exception: pass
    return skills

def skill_finden(skills, text):
    tl = text.lower()
    best, punkte = None, 0
    for s in skills:
        p = sum(1 for t in s.get("trigger", []) if t.lower() in tl)
        if p > punkte: best, punkte = s, p
    return best

def plugins_laden(app):
    tools, buttons = {}, []
    try:
        sys.path.insert(0, str(PLUGINS_DIR))
        import importlib
        for f in sorted(PLUGINS_DIR.glob("*.py")):
            if f.name.startswith("_"): continue
            try:
                mod = importlib.import_module(f.stem)
                try: mod = importlib.reload(mod)
                except Exception: pass
                reg = mod.register(app)
                tools.update(reg.get("tools", {}))
                buttons += reg.get("buttons", [])
            except Exception as e:
                print(f"Plugin {f.name}: {e}")
    except Exception as e:
        print(f"Plugins: {e}")
    return tools, buttons

# ---------- UI ----------
class QuasselKI:
    def __init__(self, root):
        self.root = root
        root.title("❯ quassel-codex v20")
        root.geometry("1040x1000"); root.minsize(780, 700)
        self.sysinfo = system_check()
        p = self.sysinfo["preset"]
        self.bock_level = tk.IntVar(value=p["bock"])
        self.stille_toleranz = tk.IntVar(value=p["stille"])
        self.autonom = tk.BooleanVar(value=True)
        # QUASSEL_VOICE=0 startet stumm (z.B. wenn im Call), sonst IMMER an: jede Ausgabe wird vorgelesen
        _voice_wunsch = os.environ.get("QUASSEL_VOICE", "1") != "0"
        self.vorlesen = tk.BooleanVar(value=(TTS_AVAILABLE or (EDGE_OK and PYGAME_OK)) and _voice_wunsch)
        self.stimme_var = tk.StringVar(value="Katja (weiblich, neural)")
        self.route_var = tk.StringVar(value="auto")  # auto | schnell | stark
        self.ton_var = tk.StringVar(value="normal")  # normal | frech | profi
        self.speed_var = tk.StringVar(value=str((QCFG.get("speed", {}) or {}).get("modus", "SMART")).upper())
        self.hw_profil = None  # v18: Hardware-Profil (Hintergrund beim Start)
        self.installierte_modelle = []
        self.modell_groessen = {}
        self.hw_empfehlung = {}
        try:
            threading.Thread(target=self._hw_start, daemon=True).start()
        except Exception: pass
        self._letztes_modell = ("", "")
        self.training = tk.BooleanVar(value=True)
        self.pc_erlaubt = tk.BooleanVar(value=False)
        self.sprecher = Sprecher(); self.sprecher.enabled = self.vorlesen.get()
        try: self.sprecher.stumm = self.stumm_var.get()
        except Exception: pass
        self.pc = SafePC(self.log)
        self.mcp = MCPClient(self.log)
        threading.Thread(target=self._mcp_autostart, daemon=True).start()
        self.skills = skills_laden()
        self.plugin_tools, self.plugin_buttons = plugins_laden(self)
        self.godmode = tk.BooleanVar(value=False)
        self.modus = tk.StringVar(value="agent")  # ask = nur reden, agent = arbeitet mit Werkzeugen
        self.letzte_user = time.time(); self.letzte_bot = time.time()
        self.redelust = 30.0; self.stimmung = "mentor"
        self.akt_projekt = None
        self.stumm_var = tk.BooleanVar(value=(os.environ.get("QUASSEL_VOICE", "1") == "0"))  # v19: absolute Stille
        self.talk_stop_var = tk.BooleanVar(value=False)  # v19: nur spontanes Reden aus
        self.finish_var = tk.BooleanVar(value=False)  # v19: Find&Finish-Loop läuft
        self.projekt_index = []  # v19: gescannte Projekte
        self.history = []  # Chatverlauf für das Modell (role/content)
        self.zusammenfassung = summary_laden()  # v17: Gedächtnis über lange Chats
        self._generating = False
        self._gen_id = 0  # Antwort-Stopp: alte Generationen werden verworfen
        self._gen_start = 0.0
        self._agent_stop = False
        self._auftrag_stand = None  # Phase 8: Retry-Tracking pro Find&Finish-Task
        self._letzter_selfcheck = "UNKNOWN"
        self._god_an = False
        self._main_id = threading.get_ident()  # Tk-Dispatcher braucht die Main-Thread-ID
        self.anhaenge = []  # Liste von Path-Strings, landen beim nächsten Prompt im Kontext
        self.live_ok = ollama_server_ok()
        # Ordner sicherstellen (Sessions, Shots, Skills, Plugins) + Live-State
        for _d in (CHATS_DIR, SHOTS, SKILLS_DIR, PLUGINS_DIR):
            try: _d.mkdir(parents=True, exist_ok=True)
            except Exception: pass
        self._live_an = False
        self._live_hist = []
        self._build_ui()
        try: self.root.protocol("WM_DELETE_WINDOW", self._beenden)
        except Exception: pass
        msg = (f"System-Check fertig! Profil: {self.sysinfo['profil']} | CPU-Kerne: {self.sysinfo['cpu']} | "
                f"RAM: {self.sysinfo['ram']}GB | GPU: {self.sysinfo['gpu']} | Frei C:: {self.sysinfo['disk_free']}GB | "
                f"Unreal: {list(self.sysinfo['editors'].keys()) or 'keins gefunden'}. {self.sysinfo['empfehlung']} "
                f"Live-Modell '{OLLAMA_MODEL}': {'bereit, ich antworte live und lese ALLES vor.' if self.live_ok else 'nicht erreichbar, ich nutze den Offline-Modus.'} "
                f"Du kannst mit mir über ALLES reden – nicht nur Unreal. v11: Ansichten (💬/🤖/🔧 oben), Live-Agent mit Bildschirm+Maus (Tab 🤖), Sessions mit Autosave, @Datei erwähnen, /permit /status /review, quassel.md-Projektregeln. /help für Befehle.")
        self.log("Quassel-KI", msg); self.sprecher.sprich("Bereit! Version 11 mit Ansichten und Live Agent.")
        self._bock_loop()
        self.root.after(60000, self._autosave_loop)

    def _beenden(self):
        try:
            if self.history:
                (CHATS_DIR / f"{datetime.now():%Y%m%d_%H%M%S}_auto.json").write_text(
                    json.dumps({"display": self.chat.get("1.0", "end-1c"), "history": self.history}, ensure_ascii=False), encoding="utf-8")
        except Exception: pass
        try: self._live_an = False
        except Exception: pass
        try: self.sprecher.stop()
        except Exception: pass
        try: self.mcp.stoppen()
        except Exception: pass
        try: self.root.destroy()
        except Exception: pass
    def _autosave_loop(self):
        try:
            if self.history:
                (CHATS_DIR / "autosave.json").write_text(
                    json.dumps({"display": self.chat.get("1.0", "end-1c"), "history": self.history[-10:]}, ensure_ascii=False), encoding="utf-8")
        except Exception: pass
        try: self.root.after(60000, self._autosave_loop)
        except Exception: pass

    def _build_ui(self):
        T = THEME
        self.root.configure(bg=T["bg"])
        # --- Sidebar (Codex) ---
        side = tk.Frame(self.root, bg=T["panel"], width=200)
        side.pack(side="left", fill="y"); side.pack_propagate(False)
        tk.Label(side, text="❯ chats", bg=T["panel"], fg=T["muted"], font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(8, 2))
        tk.Button(side, text="＋ Neuer Chat", command=self._chat_neu).pack(fill="x", padx=8)
        self.chat_liste = tk.Listbox(side, height=9, font=("Segoe UI", 9))
        self.chat_liste.pack(fill="x", padx=8, pady=4)
        self.chat_liste.bind("<<ListboxSelect>>", lambda e: self._chat_laden())
        tk.Label(side, text="❯ aktionen", bg=T["panel"], fg=T["muted"], font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
        for txt, cmd in [("📸 Shot", self.comp_shot), ("👁 Sehen", self.comp_sehen),
                         ("💾 Export", self.chat_exportieren), ("🛠 Schmiede", self.schmiede_start),
                         ("🏗 Forge", self.forge_menue)]:
            tk.Button(side, text=txt, command=cmd).pack(fill="x", padx=8, pady=1)
        tk.Label(side, text="alles Weitere: 🔧 Tools / 🤖 Agent oben", bg=T["panel"], fg=T["muted"],
                 font=("Segoe UI", 8), wraplength=180, justify="left").pack(anchor="w", padx=8, pady=(4, 0))
        if self.plugin_buttons:
            tk.Label(side, text="❯ plugins", bg=T["panel"], fg=T["muted"], font=("Consolas", 10, "bold")).pack(anchor="w", padx=8, pady=(6, 2))
            for txt, cmd in self.plugin_buttons[:6]:
                try: tk.Button(side, text=str(txt)[:22], command=cmd).pack(fill="x", padx=8, pady=1)
                except Exception: pass
        tk.Label(side, text=f"{OLLAMA_MODEL}\n19B • qwen-coder", bg=T["panel"], fg=T["muted"],
                 font=("Consolas", 8), justify="left").pack(side="bottom", anchor="w", padx=8, pady=8)
        # --- Ansichten: nur Chat / nur Tools / nur Agent (Codex-Orientierung, kein Button-Wust) ---
        self.pane_chat = tk.Frame(self.root, bg=T["bg"])
        self.pane_tools = tk.Frame(self.root, bg=T["bg"])
        self.pane_agent = tk.Frame(self.root, bg=T["bg"])
        self._ansicht_name = "chat"
        # --- Hauptbereich (wie bisher, wird danach dunkel gestylt) ---
        sysframe = tk.LabelFrame(self.pane_tools, text="💻 System (Auto-Check beim Start)", padx=8, pady=4)
        sysframe.pack(fill="x", padx=10, pady=4)
        info = (f"{self.sysinfo['profil']} | RAM {self.sysinfo['ram']}GB | {self.sysinfo['gpu'][:40]} | "
                f"C: frei {self.sysinfo['disk_free']}GB | UE: {', '.join(self.sysinfo['editors'].keys()) or '–'}")
        tk.Label(sysframe, text=info, font=("Segoe UI", 8), fg="dimgray", wraplength=620, justify="left").pack(anchor="w")
        tk.Label(sysframe, text=self.sysinfo["empfehlung"], font=("Segoe UI", 8, "italic"), wraplength=620, justify="left").pack(anchor="w")

        top = tk.Frame(self.root, padx=10, pady=4); top.pack(fill="x")
        tk.Label(top, text="❯ quassel-codex", font=("Consolas", 13, "bold")).pack(side="left")
        self.status = tk.Label(top, text="", font=("Segoe UI", 9)); self.status.pack(side="left", padx=8)
        self.btn_chat = tk.Button(top, text="💬 Chat", command=lambda: self._ansicht("chat")); self.btn_chat.pack(side="left", padx=2)
        self.btn_tools = tk.Button(top, text="🔧 Tools", command=lambda: self._ansicht("tools")); self.btn_tools.pack(side="left", padx=2)
        self.btn_agent = tk.Button(top, text="🖥 Live", command=lambda: self._ansicht("agent")); self.btn_agent.pack(side="left", padx=2)
        self.btn_ask = tk.Button(top, text="❓ Ask", command=lambda: self._modus_setzen("ask")); self.btn_ask.pack(side="left", padx=(10, 2))
        self.btn_work = tk.Button(top, text="🤖 Agent", command=lambda: self._modus_setzen("agent")); self.btn_work.pack(side="left", padx=2)
        self.live_banner = tk.Label(top, text="", font=("Segoe UI", 9, "bold")); self.live_banner.pack(side="left", padx=8)
        self.live_label = tk.Label(top, text="", font=("Segoe UI", 9, "bold")); self.live_label.pack(side="right")
        self.pane_chat.pack(side="right", fill="both", expand=True)
        self._build_agent()

        self.chat = scrolledtext.ScrolledText(self.pane_chat, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.pack(fill="both", expand=True, padx=10, pady=4)

        ctrl = tk.LabelFrame(self.pane_tools, text="Steuerung", padx=8, pady=6); ctrl.pack(fill="x", padx=10, pady=4)
        r1 = tk.Frame(ctrl); r1.pack(fill="x")
        tk.Label(r1, text="Bock:").pack(side="left")
        tk.Scale(r1, from_=0, to=100, orient="horizontal", variable=self.bock_level, length=120).pack(side="left")
        tk.Label(r1, text="Stille:").pack(side="left")
        tk.Scale(r1, from_=5, to=120, orient="horizontal", variable=self.stille_toleranz, length=120).pack(side="left")
        tk.Checkbutton(r1, text="Autonom", variable=self.autonom).pack(side="left")
        tk.Checkbutton(r1, text="🔊 Alles vorlesen", variable=self.vorlesen, command=lambda: setattr(self.sprecher, 'enabled', self.vorlesen.get())).pack(side="left")
        tk.Button(r1, text="🤫 Still!", command=self.sprecher.halt).pack(side="left", padx=4)
        self._refresh_live_label()

        r1b = tk.Frame(ctrl); r1b.pack(fill="x", pady=2)
        tk.Label(r1b, text="Stimme:", font=("Segoe UI", 9)).pack(side="left")
        stimmen = list(STIMMEN.keys())
        if not (EDGE_OK and PYGAME_OK): stimmen = ["Windows (offline)"]
        self.stimme_menü = tk.OptionMenu(r1b, self.stimme_var, *stimmen, command=self._stimme_wechsel)
        self.stimme_menü.config(font=("Segoe UI", 9)); self.stimme_menü.pack(side="left", padx=4)
        if not (EDGE_OK and PYGAME_OK):
            self.stimme_var.set("Windows (offline)")
        tk.Button(r1b, text="Test", command=lambda: self.sprecher.sprich("Hallo! Ich bin deine Quassel KI mit neuer Stimme.")).pack(side="left")
        tk.Label(r1b, text="Modell:", font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
        self.route_menü = tk.OptionMenu(r1b, self.route_var, "auto", "schnell", "stark")
        self.route_menü.config(font=("Segoe UI", 9)); self.route_menü.pack(side="left", padx=4)
        tk.Label(r1b, text="Ton:", font=("Segoe UI", 9)).pack(side="left", padx=(8, 0))
        self.ton_menü = tk.OptionMenu(r1b, self.ton_var, "normal", "frech", "profi")
        self.ton_menü.config(font=("Segoe UI", 9)); self.ton_menü.pack(side="left", padx=4)
        self._stimme_wechsel(self.stimme_var.get())

        r2 = tk.Frame(ctrl); r2.pack(fill="x", pady=3)
        tk.Checkbutton(r2, text="PC-Aktionen erlauben (fragt trotzdem nach)", variable=self.pc_erlaubt).pack(side="left")
        tk.Checkbutton(r2, text="🔓 Alles-Modus", variable=self.godmode, command=self.godmode_toggle).pack(side="left", padx=4)
        tk.Button(r2, text="PC-Check erneut", command=self.neuer_check).pack(side="left", padx=4)
        tk.Button(r2, text="Projekte finden", command=self.projekte_finden).pack(side="left", padx=4)
        tk.Button(r2, text="Unreal-Tipp", command=lambda: self.bot_sagt(random.choice(UNREAL_TIPPS))).pack(side="left", padx=4)
        self.god_banner = tk.Label(ctrl, text="", font=("Segoe UI", 9, "bold"))
        self.god_banner.pack(anchor="w")

        r3 = tk.Frame(ctrl); r3.pack(fill="x", pady=3)
        tk.Button(r3, text="Projekt öffnen in UE 🚀", command=self.projekt_oeffnen).pack(side="left")
        tk.Button(r3, text="C++ Actor erstellen 🛠️", command=self.actor_dialog).pack(side="left", padx=5)
        tk.Button(r3, text="Jetzt labern!", command=lambda: self.bot_sagt(random.choice(UNREAL_TIPPS + CODING_TIPPS))).pack(side="left", padx=5)
        self.bock_meter = tk.Label(ctrl, text="", font=("Segoe UI", 8, "italic")); self.bock_meter.pack(anchor="w")

        r3b = tk.Frame(ctrl); r3b.pack(fill="x", pady=3)
        self.stumm_btn = tk.Checkbutton(r3b, text="🔇 STUMM", variable=self.stumm_var, command=self._stumm_toggle)
        self.stumm_btn.pack(side="left")
        self.talkstop_btn = tk.Checkbutton(r3b, text="🛑 QUASSELN STOP", variable=self.talk_stop_var, command=self._talkstop_toggle)
        self.talkstop_btn.pack(side="left", padx=5)
        tk.Button(r3b, text="⛔ AGENT STOP", command=self.agent_stoppen).pack(side="left", padx=5)
        tk.Button(r3b, text="⛔ STOP ALLES", command=self.alles_stoppen).pack(side="left")
        tk.Button(r3b, text="🔎 PROJEKT SCAN", command=self.projekt_scan_start).pack(side="left", padx=5)
        self.finish_btn = tk.Checkbutton(r3b, text="🚀 FIND & FINISH", variable=self.finish_var, command=self._finish_toggle)
        self.finish_btn.pack(side="left")
        self.zustand_label = tk.Label(ctrl, text="", font=("Segoe UI", 9, "bold")); self.zustand_label.pack(anchor="w")

        r4 = tk.Frame(ctrl); r4.pack(fill="x", pady=3)
        tk.Button(r4, text="📎 Anhängen", command=self.datei_anhaengen).pack(side="left")
        tk.Button(r4, text="🧠 Memory", command=self.memory_zeigen).pack(side="left", padx=5)
        tk.Button(r4, text="📇 Index bauen", command=self.index_bauen).pack(side="left")
        self.anhang_label = tk.Label(r4, text="kein Anhang", font=("Segoe UI", 8), fg="gray")
        self.anhang_label.pack(side="left", padx=8)

        r5 = tk.Frame(ctrl); r5.pack(fill="x", pady=3)
        tk.Label(r5, text="Skill:", font=("Segoe UI", 9)).pack(side="left")
        self.skill_var = tk.StringVar(value="(wählen)")
        skillnamen = [s.get("name", "?") for s in self.skills] or ["(keine Skills)"]
        self.skill_menü = tk.OptionMenu(r5, self.skill_var, *skillnamen)
        self.skill_menü.config(font=("Segoe UI", 9)); self.skill_menü.pack(side="left", padx=4)
        tk.Button(r5, text="Skill ausführen", command=self.skill_ausfuehren).pack(side="left")
        tk.Button(r5, text="Skills neu laden", command=self.skills_neu_laden).pack(side="left", padx=5)

        bot = tk.Frame(self.pane_chat, padx=10, pady=6); bot.pack(fill="x")
        self.entry = tk.Entry(bot, font=("Segoe UI", 10)); self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.user_send()); self.entry.bind("<Key>", lambda e: self._aktiv())
        self.send_btn = tk.Button(bot, text="Senden", command=self.user_send); self.send_btn.pack(side="right")
        tk.Button(bot, text="⏹ Stopp", command=self.generierung_stoppen).pack(side="right", padx=(0, 6))
        self.mic_btn = tk.Button(bot, text="🎤", command=self.mic_toggle); self.mic_btn.pack(side="right", padx=(0, 6))
        tk.Label(self.pane_chat, text="Live-Chat mit quassel-ki (19GB) – frag einfach ALLES. @Datei erwähnen hängt sie an.", font=("Segoe UI", 8), fg="gray").pack(pady=(0,2))

        comp = tk.LabelFrame(self.pane_tools, text="👁 Sehen + 🖱 Handeln (Klicks immer mit Nachfrage!)", padx=8, pady=4)
        comp.pack(fill="x", padx=10, pady=(0,6))
        crow = tk.Frame(comp); crow.pack(fill="x")
        tk.Button(crow, text="📸 Screenshot", command=self.comp_shot).pack(side="left")
        tk.Button(crow, text="👁 Was siehst du?", command=self.comp_sehen).pack(side="left", padx=5)
        tk.Button(crow, text="🖱 Maus-Pos", command=self.comp_mauspos).pack(side="left")
        tk.Button(crow, text="👆 Klicken...", command=self.comp_klick).pack(side="left", padx=5)
        tk.Button(crow, text="⌨ Text schreiben...", command=self.comp_schreiben).pack(side="left")

        mcp = tk.LabelFrame(self.pane_tools, text="MCP-Werkzeuge (nach Bestätigung)", padx=8, pady=4)
        mcp.pack(fill="x", padx=10, pady=(0,6))
        mrow = tk.Frame(mcp); mrow.pack(fill="x")
        self.mcp_liste = tk.Listbox(mrow, height=4, font=("Segoe UI", 9)); self.mcp_liste.pack(side="left", fill="x", expand=True)
        mbtn = tk.Frame(mrow); mbtn.pack(side="right", padx=(6,0))
        tk.Button(mbtn, text="Neu laden", command=self.mcp_refresh).pack(fill="x")
        tk.Button(mbtn, text="Ausführen", command=self.mcp_run).pack(fill="x", pady=3)
        tk.Button(mbtn, text="An Modell senden", command=self.mcp_an_modell).pack(fill="x")
        prow = tk.Frame(mcp); prow.pack(fill="x", pady=(3,0))
        tk.Label(prow, text="Parameter (JSON):", font=("Segoe UI", 8)).pack(side="left")
        self.mcp_params = tk.Entry(prow, font=("Segoe UI", 9)); self.mcp_params.pack(side="left", fill="x", expand=True, padx=4)
        self.mcp_params.insert(0, '{"pfad": "", "name": ""}')
        self.mcp_ergebnis = ""

        # --- Codex-Finish: Tags, Dark-Style, Statusleiste, Sessions ---
        self.chat.tag_config("du", foreground=THEME["du"], font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("ki", foreground=THEME["ki"], font=("Segoe UI", 10, "bold"))
        self.chat.tag_config("sys", foreground=THEME["sys"], font=("Segoe UI", 9, "italic"))
        self.chat.tag_config("code", background=THEME["code_bg"], foreground=THEME["code_fg"], font=("Consolas", 10))
        self.chat.tag_config("du_body", background="#132f4c", foreground=THEME["fg"],
                             lmargin1=70, lmargin2=70, rmargin=10, spacing1=2, spacing3=10, font=("Segoe UI", 10))
        self.chat.tag_config("ki_body", background="#161b22", foreground=THEME["fg"],
                             lmargin1=10, lmargin2=10, rmargin=70, spacing1=2, spacing3=10, font=("Segoe UI", 10))
        self._dark_alles(self.root)
        self._refresh_live_label()  # Farbe nach Dark-Style neu setzen
        try: self.live_banner.config(fg=THEME["red"])
        except Exception: pass
        bar = tk.Frame(self.pane_chat, bg=THEME["panel"])
        bar.pack(fill="x", side="bottom")
        self.ctx_label = tk.Label(bar, text="", bg=THEME["panel"], fg=THEME["muted"], font=("Consolas", 8))
        self.gedaechtnis_label = tk.Label(bar, text="", bg=THEME["panel"], fg=THEME["muted"], font=("Consolas", 8))
        self.ctx_label.pack(side="right", padx=8)
        tk.Label(bar, text="❯ /help für Befehle", bg=THEME["panel"], fg=THEME["muted"], font=("Consolas", 8)).pack(side="left", padx=8)
        self._ctx_refresh()
        self._chats_refresh()
        try:  # Standard: Agent-Modus aktiv markieren
            self.btn_ask.configure(relief="raised"); self.btn_work.configure(relief="sunken")
        except Exception: pass

    def _dark_alles(self, w):
        T = THEME
        try:
            cls = w.winfo_class()
            if cls == "Frame":
                w.configure(bg=T["bg"])
            elif cls == "Label":
                try:
                    pbg = w.master.cget("bg")
                    if not str(pbg).startswith("#"): pbg = T["bg"]
                except Exception:
                    pbg = T["bg"]
                try: fstr = str(w.cget("font"))
                except Exception: fstr = ""
                w.configure(bg=pbg, fg=T["muted"] if (" 8" in fstr or "italic" in fstr) else T["fg"])
            elif cls == "Button":
                try: ist_senden = (str(w.cget("text")) == "Senden")
                except Exception: ist_senden = False
                base = "#238636" if ist_senden else T["panel2"]
                hover = "#2ea043" if ist_senden else "#2a3139"
                w.configure(bg=base, fg="white" if ist_senden else T["fg"],
                            activebackground=hover, activeforeground="white",
                            relief="flat", padx=8, pady=3, font=("Segoe UI", 9))
                def _hb(e, ww=w, h=hover):
                    try: ww.configure(bg=h)
                    except Exception: pass
                def _lb(e, ww=w, b=base):
                    try: ww.configure(bg=b)
                    except Exception: pass
                w.bind("<Enter>", _hb); w.bind("<Leave>", _lb)
            elif cls == "Entry":
                w.configure(bg=T["panel2"], fg=T["fg"], insertbackground=T["fg"], relief="flat",
                            highlightthickness=1, highlightbackground=T["border"], font=("Segoe UI", 10))
            elif cls == "Text":
                w.configure(bg=T["bg"], fg=T["fg"], insertbackground=T["fg"], relief="flat")
            elif cls == "Spinbox":
                w.configure(bg=T["panel2"], fg=T["fg"], relief="flat", buttonbackground=T["panel2"])
            elif cls == "Listbox":
                w.configure(bg=T["panel2"], fg=T["fg"], relief="flat", highlightthickness=0, selectbackground=T["accent"])
            elif cls == "Checkbutton":
                w.configure(bg=w.master.cget("bg"), fg=T["fg"], selectcolor=T["panel2"], activebackground=w.master.cget("bg"))
            elif cls == "Scale":
                w.configure(bg=w.master.cget("bg"), fg=T["muted"], troughcolor=T["panel2"], highlightthickness=0)
            elif cls == "Labelframe":
                w.configure(bg=T["panel"], fg=T["muted"])
            elif cls == "Menubutton":
                w.configure(bg=T["panel2"], fg=T["fg"], activebackground=T["accent"])
        except Exception:
            pass
        for c in w.winfo_children():
            self._dark_alles(c)

    # --- Basis ---
    def _refresh_live_label(self):
        try:
            if self.live_ok:
                self.live_label.config(text="● LIVE: quassel-ki", fg="green")
            else:
                self.live_label.config(text="○ OFFLINE-Modus", fg="orange")
        except Exception: pass
    def log(self, wer, text):
        z = datetime.now().strftime("%H:%M:%S")
        tag = "ki" if wer == "Quassel-KI" else ("du" if wer == "Du" else "sys")
        start = self.chat.index("end-1c")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"[{z}] ❯ {wer}:\n", tag)
        bodytag = "du_body" if tag == "du" else ("ki_body" if tag == "ki" else None)
        self.chat.insert("end", f"{text}\n\n", bodytag) if bodytag else self.chat.insert("end", f"{text}\n\n")
        self.chat.configure(state="disabled"); self.chat.see("end")
        self._tag_code(start, self.chat.index("end-1c"))
        try:  # Optimierung: Chat begrenzen (RAM/UI flüssig halten)
            zeilen = int(self.chat.index("end-1c").split(".")[0])
            if zeilen > 900:
                self.chat.configure(state="normal")
                self.chat.delete("1.0", "300.0")
                self.chat.configure(state="disabled")
        except Exception: pass
    def _tag_code(self, von, bis):
        try:
            self.chat.configure(state="normal")
            pos, offen = von, None
            while True:
                pos = self.chat.search("```", pos, stopindex=bis, exact=True)
                if not pos: break
                if offen is None:
                    offen = pos
                else:
                    a = self.chat.index(f"{offen} lineend +1c")
                    b = self.chat.index(f"{pos} linestart")
                    if self.chat.compare(a, "<", b):
                        self.chat.tag_add("code", a, b)
                    offen = None
                pos = self.chat.index(f"{pos}+3c")
            self.chat.configure(state="disabled")
        except Exception:
            pass
    def _ctx_refresh(self):
        try: self.ctx_label.config(text=f"{self.modus.get()} • ctx {len(self.history)}/{CTX_LIMIT} • {OLLAMA_MODEL} • Bock {self.bock_level.get()}%")
        except Exception: pass
        try: self._zustand_refresh()
        except Exception: pass
        try:
            zf = getattr(self, "zusammenfassung", "") or ""
            self.gedaechtnis_label.config(text=f"🧠 {len(zf.split())} Wörter Gedächtnis" if zf else "🧠 kein Gedächtnis")
        except Exception: pass
    # --- Sessions (Codex-Sidebar) ---
    def _chat_dateiname(self):
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    def _chats_refresh(self):
        try:
            self.chat_liste.delete(0, "end")
            for f in sorted(CHATS_DIR.glob("*.json"), reverse=True)[:30]:
                self.chat_liste.insert("end", f.stem)
        except Exception: pass
    def chat_exportieren(self):
        try:
            pf = CHATS_DIR / f"export_{datetime.now():%Y%m%d_%H%M%S}.txt"
            pf.write_text(self.chat.get("1.0", "end-1c"), encoding="utf-8")
            self.bot_sagt(f"Chat exportiert: {pf.name} (im chats-Ordner).")
        except Exception as e:
            self.bot_sagt(f"Export geht nicht: {e}")
    def _chat_neu(self):
        try:
            if self.history:
                name = re.sub(r'\W+', '_', self.history[0].get("content", "chat"))[:30] or "chat"
                (CHATS_DIR / f"{self._chat_dateiname()}_{name}.json").write_text(
                    json.dumps({"display": self.chat.get("1.0", "end-1c"), "history": self.history}, ensure_ascii=False), encoding="utf-8")
        except Exception: pass
        self.history = []
        try:
            if self.zusammenfassung: summary_speichern(self.zusammenfassung)  # Gedächtnis bleibt sessionübergreifend
        except Exception: pass
        self.chat.configure(state="normal"); self.chat.delete("1.0", "end"); self.chat.configure(state="disabled")
        self._chats_refresh(); self._ctx_refresh()
        self.bot_sagt("Neuer Chat. Gedächtnis und Fakten bleiben – alter Kram ist in der Sidebar.")
    def _chat_laden(self):
        if self._generating: self._busy_hint(); return
        try: key = self.chat_liste.get(self.chat_liste.curselection()[0])
        except Exception: return
        try:
            obj = json.loads((CHATS_DIR / f"{key}.json").read_text(encoding="utf-8"))
            self.history = obj.get("history", [])[-10:]
            self.chat.configure(state="normal"); self.chat.delete("1.0", "end")
            self.chat.insert("end", obj.get("display", "")); self.chat.configure(state="disabled")
            self._tag_code("1.0", "end"); self.chat.see("end"); self._ctx_refresh()
        except Exception: pass
    # --- Ansichten + Modi (Ask redet, Agent arbeitet) ---
    def _modus_setzen(self, modus):
        self.modus.set(modus)
        try:
            self.btn_ask.configure(relief="sunken" if modus == "ask" else "raised")
            self.btn_work.configure(relief="sunken" if modus == "agent" else "raised")
        except Exception: pass
        self._ctx_refresh()
        self.log("sys", f"Modus: {'❓ ASK (nur reden)' if modus == 'ask' else '🤖 AGENT (arbeitet mit Werkzeugen, max 8 Runden)'}")
    def _ansicht(self, name):
        self._ansicht_name = name
        for p in (self.pane_chat, self.pane_tools, self.pane_agent):
            try: p.pack_forget()
            except Exception: pass
        {"chat": self.pane_chat, "tools": self.pane_tools, "agent": self.pane_agent}[name].pack(side="right", fill="both", expand=True)
        try:
            for b, n in ((self.btn_chat, "chat"), (self.btn_tools, "tools"), (self.btn_agent, "agent")):
                b.configure(relief="sunken" if n == name else "raised")
        except Exception: pass
    def _build_agent(self):
        T = THEME
        a = self.pane_agent
        tk.Label(a, text="🤖 Live-Agent: sieht deinen Bildschirm, steuert Maus + Tastatur.", bg=T["bg"], fg=T["fg"],
                 font=("Consolas", 11, "bold"), wraplength=640, justify="left").pack(anchor="w", padx=12, pady=(12, 2))
        tk.Label(a, text="Startest du ihn, fragt er NICHT mehr pro Klick – Stopp oben, ⏹ oder Maus in die Ecke. Alles im Live-Log.",
                 bg=T["bg"], fg=T["red"], font=("Segoe UI", 9), wraplength=640, justify="left").pack(anchor="w", padx=12, pady=(0, 8))
        zrow = tk.Frame(a, bg=T["bg"]); zrow.pack(fill="x", padx=12)
        tk.Label(zrow, text="Aufgabe:", bg=T["bg"], fg=T["fg"], font=("Segoe UI", 10)).pack(side="left")
        self.agent_task = tk.Entry(zrow, font=("Segoe UI", 10)); self.agent_task.pack(side="left", fill="x", expand=True, padx=6)
        self.agent_task.insert(0, "Öffne den Epic Launcher")
        prow = tk.Frame(a, bg=T["bg"]); prow.pack(fill="x", padx=12, pady=6)
        tk.Label(prow, text="Pause (s):", bg=T["bg"], fg=T["fg"]).pack(side="left")
        self.agent_interval = tk.Spinbox(prow, from_=3, to=15, width=4); self.agent_interval.pack(side="left", padx=4)
        self.agent_interval.delete(0, "end"); self.agent_interval.insert(0, "5")
        tk.Label(prow, text="Max-Schritte:", bg=T["bg"], fg=T["fg"]).pack(side="left", padx=(10, 0))
        self.agent_max = tk.Spinbox(prow, from_=3, to=40, width=4); self.agent_max.pack(side="left", padx=4)
        self.agent_max.delete(0, "end"); self.agent_max.insert(0, "15")
        tk.Label(prow, text="Denker:", bg=T["bg"], fg=T["fg"]).pack(side="left", padx=(10, 0))
        tk.Label(prow, text=AGENT_MODEL, bg=T["bg"], fg=T["muted"], font=("Consolas", 9)).pack(side="left")
        brow = tk.Frame(a, bg=T["bg"]); brow.pack(fill="x", padx=12, pady=4)
        tk.Button(brow, text="▶ Live starten", command=self.live_start).pack(side="left")
        tk.Button(brow, text="⏹ Live-Stopp", command=lambda: self.live_stopp("manuell gestoppt")).pack(side="left", padx=6)
        self.live_log = scrolledtext.ScrolledText(a, wrap="word", state="disabled", font=("Consolas", 9), height=18)
        self.live_log.pack(fill="both", expand=True, padx=12, pady=8)
    def _live_log(self, text):
        if threading.get_ident() != self._main_id:
            self._ui(lambda: self._live_log(text)); return
        try:
            self.live_log.configure(state="normal")
            self.live_log.insert("end", f"[{datetime.now():%H:%M:%S}] {text}\n")
            self.live_log.configure(state="disabled"); self.live_log.see("end")
        except Exception: pass
    def _live_banner_update(self):
        try:
            self.live_banner.config(text="🔴 LIVE – steuert Maus/Tastatur" if self._live_an else "")
        except Exception: pass
    def live_start(self):
        aufgabe = self.agent_task.get().strip()
        if not aufgabe:
            self._live_log("Keine Aufgabe eingetragen."); return
        if self._live_an: return
        if not messagebox.askyesno("Live-Modus starten?", f"Ich übernehme Maus + Tastatur für:\n{aufgabe}\n\nKein Nachfragen pro Klick mehr. Stopp: ⏹ Live-Stopp, 🤫, oder Maus in die Bildschirm-Ecke."):
            return
        try: self.agent_interval.get(); self.agent_max.get()
        except Exception: pass
        self._live_an = True; self._live_hist = []
        self._ansicht("agent"); self._live_banner_update()
        self.sprecher.sprich("Live Modus an. Ich sehe deinen Bildschirm und lege los.")
        self.pc.aktion_loggen(f"LIVE-START: {aufgabe}")
        threading.Thread(target=self._live_loop, args=(aufgabe,), daemon=True).start()
    def live_stopp(self, grund="fertig"):
        if not self._live_an: return
        self._live_an = False
        self._ui(self._live_banner_update)
        self.pc.aktion_loggen(f"LIVE-STOPP: {grund}")
        self.bot_sagt(f"Live-Modus aus ({grund}). Ich quassle wie gewohnt weiter.")
    def _live_loop(self, aufgabe):
        schritte, maximum = 0, 15
        try: maximum = max(3, min(40, int(self.agent_max.get())))
        except Exception: pass
        while self._live_an and schritte < maximum:
            schritte += 1
            try:
                pf, sk, err = agent_shot()
                if err:
                    self._live_log(f"Shot-Fehler: {err}"); break
                try:
                    desc = bild_sehen("Describe this screenshot in detail: active windows, texts, buttons, cursor position.", pf)
                except Exception as e:
                    self._live_log(f"Vision pausiert: {e} – neuer Versuch gleich.")
                    time.sleep(5); continue
                mx, my = (0, 0)
                try:
                    if PYAUTO_OK: mx, my = _pag.position()
                except Exception: pass
                verlauf = [{"role": "system", "content": LIVE_SYS},
                           {"role": "user", "content": f"Aufgabe: {aufgabe}\nMaus: x={mx}, y={my} (echt), Bild: 1280px breit (Skala beachten)\nSeheindruck: {desc[:1500]}\nBisher: {' | '.join(self._live_hist[-4:]) or 'Start'}"}]
                try:
                    antwort = ollama_chat_once(verlauf, AGENT_MODEL, tokens=150)  # kurz = schneller Loop
                except Exception as e:
                    self._live_log(f"Denker-Fehler: {e}"); time.sleep(5); continue
                aktion = self._live_parse(antwort)
                if not aktion:
                    kurz = antwort.strip().replace("\n", " ")[:220] or "(leer)"
                    self._live_log(f"💬 {kurz}")
                    self._live_hist.append("Status: " + kurz)
                else:
                    werkzeug = aktion.get("tool", "")
                    if werkzeug == "done" or werkzeug == "say" and aktion.get("fertig"):
                        self.live_stopp(str(aktion.get("text", aktion.get("ergebnis", "fertig"))[:300])); return
                    if werkzeug == "say":
                        txt = str(aktion.get("text", ""))[:300]
                        self._live_log(f"💬 {txt}"); self.sprecher.sprich(txt)
                        self._live_hist.append("Gesagt: " + txt)
                    elif werkzeug == "click":
                        x, y = int(float(aktion.get("x", 0)) * sk), int(float(aktion.get("y", 0)) * sk)
                        self._live_log(f"🖱 Klick {x},{y}")
                        self.pc.aktion_loggen(f"LIVE click {x},{y}")
                        try:
                            if PYAUTO_OK: _pag.moveTo(x, y, duration=0.4); _pag.click()
                        except Exception as e:
                            if "FailSafe" in type(e).__name__:
                                self.live_stopp("Failsafe: Maus in der Ecke"); return
                            self._live_log(f"Klick-Fehler: {e}")
                        self._live_hist.append(f"Klick {x},{y} getan")
                    elif werkzeug == "type":
                        txt = str(aktion.get("text", ""))[:500]
                        self._live_log(f"⌨ Tippe {len(txt)} Zeichen")
                        self.pc.aktion_loggen(f"LIVE type {len(txt)} Zeichen")
                        try:
                            if PYAUTO_OK: _pag.write(txt, interval=0.02)
                        except Exception as e:
                            self._live_log(f"Tipp-Fehler: {e}")
                        self._live_hist.append("Getippt")
                    elif werkzeug == "key":
                        taste = str(aktion.get("name", "enter")).lower()
                        self._live_log(f"⌨ Taste {taste}")
                        try:
                            if PYAUTO_OK: _pag.press(taste)
                        except Exception as e:
                            self._live_log(f"Tasten-Fehler: {e}")
                        self._live_hist.append(f"Taste {taste}")
                    elif werkzeug == "wait":
                        time.sleep(max(1, min(8, float(aktion.get("sec", 2)))))
                        self._live_hist.append("Gewartet")
                    else:
                        self._live_log(f"Unbekannte Aktion: {werkzeug}")
                pause = 5
                try: pause = max(3, min(15, int(self.agent_interval.get())))
                except Exception: pass
                for _ in range(pause * 2):
                    if not self._live_an: return
                    time.sleep(0.5)
            except Exception as e:
                self._live_log(f"Schritt-Fehler: {e}")
        self.live_stopp("Max-Schritte erreicht" if schritte >= maximum else "beendet")
    def _live_parse(self, antwort):
        try:
            m = re.search(r"```action\s*(\{.*?\})\s*```", antwort, re.S)
            if not m: return None
            obj = json.loads(m.group(1))
            if isinstance(obj, dict) and "tool" in obj: return obj
        except Exception: pass
        return None

    # --- Slash-Befehle (Codex) ---
    def _befehl(self, m):
        cmd = m.split()[0].lower()
        if cmd == "/help":
            self.bot_sagt("❯ Befehle:\n" + "\n".join(sorted(BEFEHLE))); return True
        if cmd == "/neu": self._chat_neu(); return True
        if cmd == "/clear":
            self.chat.configure(state="normal"); self.chat.delete("1.0", "end"); self.chat.configure(state="disabled"); return True
        if cmd == "/still":
            self.sprecher.halt(); self.bot_sagt("Ok ok, ich bin still. (Weiter geht's mit /laut)"); return True
        if cmd == "/laut":
            self.vorlesen.set(True); self.sprecher.enabled = True; self.bot_sagt("Laut wieder an!"); return True
        if cmd == "/leise":
            self.vorlesen.set(False); self.sprecher.enabled = False; self.sprecher.halt(); self.log("sys", "Stimme aus."); return True
        if cmd == "/shot": self.comp_shot(); return True
        if cmd == "/sehen": self.comp_sehen(); return True
        if cmd == "/maus": self.comp_mauspos(); return True
        if cmd == "/memory": self.memory_zeigen(); return True
        if cmd == "/index": self.index_bauen(); return True
        if cmd == "/tipp": self.bot_sagt(random.choice(UNREAL_TIPPS + CODING_TIPPS)); return True
        if cmd == "/modell":
            try:
                rollen = ((QCFG.get("modelle", {}) or {}).get("rollen", {}) or {})
                inst = self.installierte_modelle or ["(Hardware-Check läuft noch)"]
                info = " | ".join(f"{r}={ROUTER.waehle_modell(r, self.installierte_modelle or None, rollen or None) or '?'}" for r in ("fast", "coding", "vision")) if _HAT_QUASSEL_PAKET else "Router aus"
                self.bot_sagt(f"Rollen: {info}. Installiert: {', '.join(inst[:6])}. Lokal, offline-fähig.")
            except Exception:
                self.bot_sagt(f"Modell: {OLLAMA_MODEL} + Vision: {VISION_MODEL}. Lokal, offline-fähig.")
            return True
        if cmd == "/ctx":
            self.bot_sagt(f"Kontext: {len(self.history)}/{CTX_LIMIT} Nachrichten. Memory: {len(memory_laden().get('fakten', []))} Fakten."); return True
        if cmd == "/skill": self.skill_ausfuehren(); return True
        if cmd == "/plugin": self.ue_plugin_dialog(); return True
        if cmd == "/god":
            self.godmode.set(not self.godmode.get()); self.godmode_toggle(); return True
        if cmd == "/export": self.chat_exportieren(); return True
        if cmd == "/mode":
            wunsch = (m.split()[1].lower() if len(m.split()) > 1 else "")
            if wunsch in ("ask", "agent"): self._modus_setzen(wunsch)
            else: self.bot_sagt(f"Modus ist {self.modus.get()}. /mode ask|agent wechselt.")
            return True
        if cmd == "/commit": self.git_commit_flow(); return True
        if cmd == "/ton":
            wunsch = (m.split()[1].lower() if len(m.split()) > 1 else "")
            if wunsch in TONS: self.ton_var.set(wunsch); self.bot_sagt(f"Ton: {wunsch}.")
            else: self.bot_sagt(f"Ton ist {self.ton_var.get()}. /ton normal|frech|profi.")
            return True
        if cmd in ("/verlauf", "/gedaechtnis"):
            zf = getattr(self, "zusammenfassung", "") or summary_laden()
            if not zf:
                self.bot_sagt("Gedächtnis ist noch leer – es füllt sich, sobald ein Chat lang genug wird."); return True
            self.bot_sagt("🧠 Mein Gedächtnis:\n" + zf[:900])
            return True
        if cmd == "/geruest": self.forge_geruest_dialog(); return True
        if cmd == "/tasks":
            s = m.split(None, 1)[1] if len(m.split(None, 1)) > 1 else ""
            self.bot_sagt(self.mcp.aufrufen("lokal/tasks_status", {"spiel": s}, self._mcp_ctx()) if s else "Nutzen: /tasks Spielname"); return True
        if cmd == "/logcheck":
            o = str(self.akt_projekt.parent) if self.akt_projekt else ""
            self.bot_sagt(self.mcp.aufrufen("lokal/log_analyse", {"projekt_ordner": o}, self._mcp_ctx()) if o else "Kein Projekt aktiv – erst 'Projekte finden'."); return True
        if cmd == "/impact":
            k = m.split(None, 1)[1] if len(m.split(None, 1)) > 1 else ""
            o = str(self.akt_projekt.parent / "Source") if self.akt_projekt else ""
            self.bot_sagt(self.mcp.aufrufen("lokal/impact_check", {"ordner": o, "klasse": k}, self._mcp_ctx()) if (o and k) else "Nutzen: /impact KlassenName (braucht aktives Projekt)"); return True
        if cmd == "/schmiede": self.schmiede_start(); return True
        if cmd == "/status":
            modus = "🔓 VOLL (Alles)" if self._god_an else ("🟡 AUTO (PC erlaubt)" if self.pc_erlaubt.get() else "🟢 LESEN (Nachfrage)")
            stimme = self.stimme_var.get() if self.vorlesen.get() else "aus"
            self.bot_sagt(f"❯ Status: Speed {self.speed_var.get()} | ctx {len(self.history)}/{CTX_LIMIT} (Budget {getattr(self, '_letztes_ctx_budget', NUM_CTX)}) | Modus {modus} | Chat-Modus {self.modus.get()} | Stimme {stimme} | Live {'AN' if self._live_an else 'aus'} | Gedächtnis {len((getattr(self,'zusammenfassung','') or '').split())} W | Skills {len(self.skills)} | Chats {len(list(CHATS_DIR.glob('*.json')))}")
            try:
                if self.hw_profil: self.bot_sagt("```\n" + HW.profil_text(self.hw_profil)[:1200] + "\n```")
                else: self.bot_sagt("Hardware-Check läuft noch im Hintergrund…")
            except Exception: pass
            return True
        if cmd == "/speed":
            wunsch = (m.split()[1].upper() if len(m.split()) > 1 else "")
            if wunsch in ("FAST", "BALANCED", "SMART", "MAXIMUM"):
                self.speed_var.set(wunsch); self.bot_sagt(f"Speed: {wunsch}.")
            else: self.bot_sagt(f"Speed ist {self.speed_var.get()}. /speed FAST|BALANCED|SMART|MAXIMUM.")
            return True
        if cmd == "/stumm":
            self.stumm_var.set(not self.stumm_var.get()); self._stumm_toggle(); return True
        if cmd == "/quasseln":
            self.talk_stop_var.set(not self.talk_stop_var.get()); self._talkstop_toggle(); return True
        if cmd == "/agentstop": self.agent_stoppen(); return True
        if cmd == "/stopalles": self.alles_stoppen(); return True
        if cmd == "/scan":
            ziel = m.split(None, 1)[1] if len(m.split(None, 1)) > 1 else ""
            self.projekt_scan_start(ziel or None); return True
        if cmd == "/finish":
            self.finish_var.set(not self.finish_var.get()); self._finish_toggle(); return True
        if cmd in ("/permit", "/permissions"):
            stufe = (m.split()[1].lower() if len(m.split()) > 1 else "")
            if stufe in ("voll", "yolo", "full"):
                self.godmode.set(True); self.godmode_toggle()
            elif stufe in ("auto", "an"):
                self.godmode.set(False); self.pc.unbegrenzt = False; self._god_an = False
                self.pc_erlaubt.set(True)
                try: self.god_banner.config(text="")
                except Exception: pass
                self.bot_sagt("Modus 🟡 AUTO: PC-Aktionen erlaubt, fragen aber weiter nach.")
            else:
                self.godmode.set(False); self.pc.unbegrenzt = False; self._god_an = False
                self.pc_erlaubt.set(False)
                try: self.god_banner.config(text="")
                except Exception: pass
                self.bot_sagt("Modus 🟢 LESEN: alles fragt nach. (/permit auto|voll für mehr)")
            return True
        if cmd == "/review":
            if not self.anhaenge:
                self.bot_sagt("Häng erst Code an (📎 oder @Dateiname), dann /review – ich zerlege ihn: Bugs, Stil, Performance."); return True
            self._aktiv(); self.log("Du", "[Review angefragt]")
            self.history.append({"role": "user", "content": "Reviewe die angehängten Dateien gnadenlos aber fair: 1. Bugs 2. Stil 3. Performance 4. Fix-Vorschlag mit Code."})
            self._ctx_kuerzen()
            if ollama_server_ok(): self._live_frage(list(self.history))
            else: self.bot_sagt("Offline – Review braucht das Live-Modell.")
            return True
        if cmd.startswith("/"):
            self.bot_sagt(f"Unbekannt: {cmd}. /help zeigt alle."); return True
        return False
    def _aktiv(self): self.letzte_user = time.time(); self.redelust = max(0, self.redelust - 2)
    def _ui(self, fn):
        """Tkinter nur aus dem Main-Thread anfassen (fixt RuntimeError aus Worker-Threads)."""
        try:
            if threading.get_ident() == self._main_id:
                fn()
            else:
                self.root.after(0, fn)
        except (RuntimeError, tk.TclError):
            pass
        except Exception:
            pass
    def bot_sagt(self, t):
        if threading.get_ident() != self._main_id:
            self._ui(lambda: self.bot_sagt(t)); return
        """Jede Ausgabe wird geloggt UND vorgelesen (außer bei STUMM)."""
        self.log("Quassel-KI", t)
        try:
            if not self.stumm_var.get():
                self.sprecher.sprich(t)
        except Exception:
            try: self.sprecher.sprich(t)
            except Exception: pass
        self.history.append({"role": "assistant", "content": str(t)[:1500]})
        self._ctx_kuerzen()
        self.letzte_bot = time.time(); self.redelust = max(0, self.redelust - 25)
    # --- Mikrofon: lokal per Whisper (freihändig), ohne Cloud ---
    def mic_toggle(self):
        try:
            import sounddevice as _sd
        except ImportError:
            self.bot_sagt("Mikro fehlt: pip install sounddevice faster-whisper"); return
        if getattr(self, "_mic_an", False):
            self._mic_an = False
            try: self.mic_btn.config(text="🎤")
            except Exception: pass
            return
        self._mic_an = True
        try: self.mic_btn.config(text="🔴")
        except Exception: pass
        self.log("sys", "🎤 hört zu… nochmal klicken = fertig.")
        threading.Thread(target=self._mic_arbeit, daemon=True).start()
    def _mic_arbeit(self):
        try:
            import sounddevice as _sd
            import numpy as _np
            frames = []
            def _cb(indata, _frames, _time, _status):
                if self._mic_an: frames.append(indata.copy())
            with _sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=_cb):
                while self._mic_an:
                    _sd.sleep(200)
            if not frames:
                self._ui(lambda: self.log("sys", "🎤 nichts aufgenommen.")); return
            import numpy as _np2
            audio = _np2.concatenate(frames, axis=0).flatten()
            self._ui(lambda: self.log("sys", "🎤 schreibe… (Whisper lädt ggf. 150MB beim 1. Mal)"))
            from faster_whisper import WhisperModel
            if getattr(self, "_mic_modell", None) is None:
                self._mic_modell = WhisperModel("base", device="cpu", compute_type="int8")
            segmente, _ = self._mic_modell.transcribe(audio, language="de")
            text = " ".join(s.text for s in segmente).strip()
            if not text:
                self._ui(lambda: self.log("sys", "🎤 nichts verstanden.")); return
            self._ui(lambda: self._mic_einsetzen(text))
        except Exception as e:
            self._ui(lambda e=e: self.log("sys", f"🎤 Fehler: {e}"))
        finally:
            self._mic_an = False
            try: self._ui(lambda: self.mic_btn.config(text="🎤"))
            except Exception: pass
    def _mic_einsetzen(self, text):
        self.entry.delete(0, "end"); self.entry.insert(0, text)
        self.log("sys", f"🎤 gehört: {text[:150]}")
        self.user_send()  # freihändig: direkt los
    def git_commit_flow(self):
        basis = self.akt_projekt.parent if self.akt_projekt else WORKSPACE
        repo = git_repo_suchen(basis)
        if not repo:
            self.bot_sagt("Kein Git-Repo (weder Projekt noch Workspace)."); return
        code, status = git_laufen(["status", "--short"], repo)
        if not status.strip():
            self.bot_sagt("Git sauber – nichts zu committen."); return
        code, diff = git_laufen(["diff", "--stat"], repo)
        vorschlag = "update"
        if ollama_server_ok():
            try:
                vorschlag = ollama_chat_once([
                    {"role": "system", "content": "Erzeuge EINE kurze Git-Commit-Message (max 72 Zeichen, Präfix feat/fix/docs wo passend). Nur die Message."},
                    {"role": "user", "content": f"Status:\n{status[:1500]}\nDiffstat:\n{diff[:1500]}"}], FAST_MODEL, 120, 60).strip().strip('"')[:72] or "update"
            except Exception: pass
        nachricht = simpledialog.askstring("Git-Commit", f"Repo: {repo}\n{status[:800]}\n\nNachricht:", initialvalue=vorschlag, parent=self.root)
        if not nachricht: return
        if not messagebox.askyesno("Committen?", f"git commit -am\n'{nachricht}'\nin {repo}?"):
            self.log("Quassel-KI", "(Commit abgebrochen.)"); return
        code, out = git_laufen(["commit", "-am", nachricht], repo)
        self.pc.aktion_loggen(f"git_commit in {repo}: {nachricht}")
        self.bot_sagt(f"Commit: Exit {code}\n{(out.strip() or '(ok)')[:800]}")
    def _router_modell(self, frage):
        """v18: Brain-Router -> (modell, protokoll). Echte Entscheidung, geloggt."""
        try:
            if _HAT_QUASSEL_PAKET and (QCFG.get("modelle", {}) or {}).get("auto_select", True) \
                    and self.installierte_modelle:
                proto = ROUTER.entscheidungs_protokoll(frage, self.speed_var.get())
                rollen = ((QCFG.get("modelle", {}) or {}).get("rollen", {}) or None)
                # v20-Phase2: Kapazitätsschutz – zu große Modelle werden nie gewählt
                modell = ROUTER.waehle_modell(proto["rolle"], self.installierte_modelle or None,
                                              rollen, self._max_gb(), getattr(self, "modell_groessen", None))
                if modell: return modell, proto
        except Exception: pass
        return None, {"schwere": "?", "warum": "Fallback", "rolle": "?", "speed": self.speed_var.get()}

    def _akt_projekt_name(self):
        try:
            if self.akt_projekt:
                return Path(str(self.akt_projekt)).parent.name or Path(str(self.akt_projekt)).name
        except Exception: pass
        return ""
    def _memory2_block(self, frage):
        """v18: typisiertes Retrieval (nur Relevantes, Unsicheres markiert)."""
        try:
            if _HAT_QUASSEL_PAKET and (QCFG.get("memory", {}) or {}).get("retrieval", True):
                lim = int((QCFG.get("memory", {}) or {}).get("limit_fakten", 8))
                treffer = MEM2.abrufen(str(MEMORY2_PFAD), frage, limit_fakten=lim,
                                       projekt=self._akt_projekt_name() or None)
                if treffer: return "Gelerntes Wissen (mit Quelle, Unsicheres markiert):\n" + MEM2.als_systemtext(treffer)
        except Exception: pass
        return ""

    def _self_check(self, aufgabe, werkzeug_spuren):
        """v18: echte Prüfung nach Agent-Arbeit (Schema, temp 0). Gibt (confidence, restrisiken)."""
        try:
            if not (_HAT_QUASSEL_PAKET and (QCFG.get("agent", {}) or {}).get("self_check", True)):
                return "UNKNOWN", ""
            spuren = "\n".join(werkzeug_spuren[-6:])[:2500]
            obj = ollama_json([
                {"role": "system", "content": "Du prüfst die Arbeit eines KI-Agenten. Antworte NUR per Schema, ehrlich. "
                    "confidence ist HIGH/MEDIUM/LOW. tests_ok nur true wenn Tests wirklich liefen."},
                {"role": "user", "content": f"Aufgabe: {aufgabe[:600]}\n\nWerkzeug-Spuren:\n{spuren}"}],
                SELF_CHECK_SCHEMA, self._schnell_modell(), 90, 250)
            conf = str(obj.get("confidence", "UNKNOWN")).upper()
            if conf not in ("HIGH", "MEDIUM", "LOW"): conf = "UNKNOWN"
            risiko = str(obj.get("restrisiken", ""))[:300]
            erfunden = "JA" if obj.get("etwas_erfunden") else "nein"
            self._ui(lambda: self.log("sys", f"🔍 SELF CHECK: verstanden={obj.get('verstanden')} erfunden={erfunden} "
                      f"dateien_ok={obj.get('dateien_ok')} tests_ok={obj.get('tests_ok')} CONFIDENCE={conf}"
                      + (f" Risiken: {risiko}" if risiko and risiko.lower() not in ("keine", "none", "") else "")))
            return conf, risiko
        except Exception:
            return "UNKNOWN", ""

    def _lesson_speichern(self, aufgabe, werkzeug_spuren, conf):
        """v18: Feedback-Loop – Lesson für ähnliche Aufgaben merken."""
        try:
            if not _HAT_QUASSEL_PAKET: return
            spuren = "\n".join(werkzeug_spuren[-4:])[:1500]
            obj = ollama_json([
                {"role": "system", "content": "Fasse die Agent-Arbeit als Lesson für ähnliche Aufgaben zusammen. "
                    "lesson = der eine Satz, der beim nächsten Mal hilft. Ehrlich bei Misserfolg."},
                {"role": "user", "content": f"Aufgabe: {aufgabe[:500]}\nSpuren:\n{spuren}\nConfidence: {conf}"}],
                LESSON_SCHEMA, self._schnell_modell(), 90, 250)
            lesson = str(obj.get("lesson", "")).strip()
            if len(lesson) > 15:
                MEM2.hinzufuegen(str(MEMORY2_PFAD), "lesson",
                    f"{obj.get('aufgabe', aufgabe)[:150]} -> {lesson}",
                    quelle="agent-feedback", vertrauen=0.6 if conf == "HIGH" else 0.5,
                    projekt=self._akt_projekt_name(), wichtigkeit=4)
        except Exception: pass

    def _max_gb(self):
        """Kapazitätsdeckel: yaml gewinnt, sonst Hardware-Profil."""
        try:
            m = (QCFG.get("modelle", {}) or {}).get("max_modell_gb")
            if m: return float(m)
            return float((getattr(self, "hw_empfehlung", {}) or {}).get("max_modell_gb", 0) or 0) or None
        except Exception:
            return None
    def _schnell_modell(self):
        try:
            if _HAT_QUASSEL_PAKET:
                rollen = ((QCFG.get("modelle", {}) or {}).get("rollen", {}) or None)
                m = ROUTER.waehle_modell("fast", self.installierte_modelle or None, rollen,
                                         self._max_gb(), getattr(self, "modell_groessen", None))
                if m: return m
        except Exception: pass
        return FAST_MODEL

    # --- v19: Projekt-Scan + Find&Finish ---
    PROJEKT_INDEX_PFAD = WORKSPACE / "quassel-ki" / "projekt_index_v19.json"
    def _scan_pfade(self, extra=None):
        pfade = []
        try: pfade = list(((QCFG.get("projekte", {}) or {}).get("scan_pfade", []) or []))
        except Exception: pass
        pfade = [str(Path(p).expanduser()) for p in pfade if p]
        if extra: pfade.append(str(extra))
        if str(WORKSPACE) not in pfade: pfade.append(str(WORKSPACE))
        return [p for p in pfade if Path(p).is_dir()]
    def projekt_scan_start(self, ziel=None):
        if not _HAT_QUASSEL_PAKET or PROJ is None:
            self.bot_sagt("Projekt-Scanner nicht verfügbar (quassel-Paket fehlt)."); return
        self.log("sys", "🔎 Projekt-Scan läuft (nur konfigurierte Ordner)…")
        threading.Thread(target=self._projekt_scan_arbeit, args=(ziel,), daemon=True).start()
    def _projekt_scan_arbeit(self, ziel=None):
        try:
            tiefe = int(((QCFG.get("projekte", {}) or {}).get("tiefe", 2) or 2))
            index = PROJ.scan_verzeichnisse(self._scan_pfade(ziel), tiefe=tiefe)
            self.projekt_index = index
            try:
                self.PROJEKT_INDEX_PFAD.write_text(json.dumps(index, ensure_ascii=False, indent=1)[:500000], encoding="utf-8")
            except Exception: pass
            n_tasks = sum(len(p.get("tasks", [])) for p in index)
            self._ui(lambda: self.bot_sagt(f"🔎 Scan fertig: {len(index)} Projekte, {n_tasks} Aufgaben-Kandidaten.\n" + PROJ.tasks_bericht(index)))
        except Exception as e:
            self._ui(lambda e=e: self.log("sys", f"Scan-Fehler: {e}"))
    def _finish_toggle(self):
        an = self.finish_var.get()
        if an:
            if self._generating:
                self.finish_var.set(False); self.bot_sagt("Erst läuft noch was – danach 🚀 nochmal."); return
            self._agent_stop = False
            self.log("sys", "🚀 FIND & FINISH an: nur sichere Tasks (Confidence hoch, Risiko LOW/MEDIUM), Git-Checkpoint pro Task.")
            threading.Thread(target=self._finish_loop, daemon=True).start()
        else:
            self.log("sys", "🚀 FIND & FINISH aus.")
        self._zustand_refresh()
    def _finish_loop(self):
        try:
            if not self.projekt_index:
                self._ui(lambda: self.log("sys", "🚀 Erst Scan, dann Finish…"))
                self._projekt_scan_arbeit()
            tiefe_cfg = (QCFG.get("projekte", {}) or {})
            min_conf = float(tiefe_cfg.get("min_confidence", 0.8) or 0.8)
            max_risk = str(tiefe_cfg.get("max_risk", "MEDIUM") or "MEDIUM")
            runden = 0
            while self.finish_var.get() and not self._agent_stop and runden < 10:
                runden += 1
                top = PROJ.top_tasks(self.projekt_index, min_confidence=min_conf, max_risk=max_risk, limit=1)
                if not top:
                    self._ui(lambda: self.bot_sagt("🚀 Fertig: keine sicheren offenen Tasks mehr (Rest braucht dich)."))
                    break
                t = top[0]
                self._finish_eine_aufgabe(t)
            if not self._agent_stop:
                self._ui(lambda: self.bot_sagt("🚀 Find&Finish-Runde beendet."))
        except Exception as e:
            self._ui(lambda e=e: self.log("sys", f"🚀 Finish-Fehler: {e}"))
        finally:
            try: self.finish_var.set(False)
            except Exception: pass
            self._zustand_refresh()
    def _finish_eine_aufgabe(self, t):
        # Phase 8 Zyklus: Impact -> Retry-Gate -> Checkpoint -> Agent -> Testnachweis -> Doku
        name, pfad = t["projekt"], t["pfad"]
        task_id = f"{name}:{t.get('datei','')}:{t.get('zeile','')}:{t['text'][:40]}"
        if not hasattr(self, "_auftrag_stand") or self._auftrag_stand is None:
            self._auftrag_stand = AUF.neuer_stand() if _HAT_QUASSEL_PAKET else {}
        try:
            if _HAT_QUASSEL_PAKET and not AUF.darf_nochmal(self._auftrag_stand, task_id):
                self._ui(lambda: self.log("sys", f"🚀 Übersprungen (3 Versuche verbraucht, Ursache dokumentiert)."))
                return
        except Exception: pass
        self._ui(lambda: self.log("sys", f"🚀 Task [{t['risk']}/{t['confidence']:.2f}] {t['text'][:80]} ({name})"))
        # 1. Impact: HIGH an der Fundstelle -> nicht autonom, dem Nutzer vorlegen
        try:
            if _HAT_QUASSEL_PAKET and t.get("datei"):
                a = IMP.analysieren(pfad, Path(t["datei"]).stem, max_treffer=20)
                if a.get("risiko") in ("HIGH", "CRITICAL"):
                    AUF.fehlversuch(self._auftrag_stand, task_id, f"Impact {a['risiko']} – braucht dich")
                    self._ui(lambda: self.bot_sagt(f"🚀 Task braucht dich (Impact {a['risiko']}): {t['text'][:100]}\n{IMP.bericht(a)[:600]}"))
                    return
        except Exception: pass
        # 2. Git-Checkpoint: eigener Branch + HEAD merken (Rollback), kein Push
        head = ""
        try:
            slug = re.sub(r"\W+", "-", t["text"].lower())[:30].strip("-") or "task"
            erg = self.mcp.aufrufen("lokal/git_branch", {"ordner": pfad, "name": f"quassel/auto-{slug}"}, self._mcp_ctx())
            self._ui(lambda e=str(erg)[:150]: self.log("sys", f"🌿 Checkpoint: {e}"))
            if _HAT_QUASSEL_PAKET:
                head = AUF.checkpoint_head(pfad)
        except Exception: pass
        # Projektregeln lesen (haben Priorität)
        regeln_text = ""
        try:
            for p in (p for p in self.projekt_index if p.get("pfad") == pfad):
                for r in p.get("regeln", [])[:3]:
                    rp = Path(pfad) / r
                    if rp.is_file() and rp.stat().st_size < 50000:
                        regeln_text += f"\n--- {r} ---\n" + rp.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception: pass
        wo = f" (Fundstelle {t.get('datei', '')}:{t.get('zeile', '')})" if t.get("datei") else ""
        aufgabe = (f"Projekt {name} in {pfad}. Aufgabe{wo}: {t['text']}. "
            "Arbeite NUR in diesem Projektordner. Lies erst relevante Dateien, plane, ändere minimal, "
            "teste (Build/Tests wenn vorhanden), prüfe den Diff. Halte dich an diese Projektregeln:"
            + (regeln_text or " (keine Regeldateien gefunden)"))
        fehler_txt = ""
        try:
            self._agent_arbeit(aufgabe)  # nutzt Router, Permit, Self-Check, Lessons
            if getattr(self, "_letzter_selfcheck", "UNKNOWN") == "LOW":
                fehler_txt = "Self-Check LOW"
        except Exception as e:
            fehler_txt = str(e)[:200]
            self._ui(lambda e=e: self.log("sys", f"🚀 Task-Fehler: {e}"))
        # 3. Testnachweis: geänderte Dateien seit Checkpoint prüfen
        nachweis = "keine Änderungen"
        try:
            if _HAT_QUASSEL_PAKET and head:
                geaendert = AUF.geaenderte_dateien(pfad, head)
                if geaendert:
                    nachweis = self._testnachweis(pfad, geaendert)
        except Exception as e:
            nachweis = f"Nachweis fehlgeschlagen: {e}"
        self._ui(lambda n=nachweis: self.log("sys", f"🧪 Testnachweis: {n[:300]}"))
        # 4. Fehlversuch oder Erfolg verbuchen (3 Strikes -> dokumentieren + nächste)
        try:
            if _HAT_QUASSEL_PAKET:
                if fehler_txt or nachweis.startswith("FEHLER"):
                    aufg = AUF.fehlversuch(self._auftrag_stand, task_id, fehler_txt or nachweis)
                    if aufg:
                        grund = "; ".join(f.get("grund", "") for f in self._auftrag_stand["aufgaben"][task_id]["fehler"])
                        MEM2.hinzufuegen(str(MEMORY2_PFAD), "lesson",
                            f"{name}: {t['text'][:100]} aufgegeben nach 3 Versuchen. Ursachen: {grund[:200]}",
                            quelle="find-finish", vertrauen=0.8, projekt=name, wichtigkeit=4)
                        self._ui(lambda: self.log("sys", "🚀 3 Versuche verbraucht – Ursache dokumentiert, nächste Aufgabe."))
                else:
                    AUF.erfolg(self._auftrag_stand, task_id, nachweis[:150])
                    self.mcp.aufrufen("lokal/doku_update", {"spiel": name, "eintrag": f"🚀 {t['text'][:120]} – {nachweis[:200]}"}, self._mcp_ctx())
        except Exception: pass
        try:  # Index für dieses Projekt auffrischen
            for i, p in enumerate(self.projekt_index):
                if p.get("pfad") == pfad:
                    self.projekt_index[i] = PROJ.projekt_analysieren(pfad)
                    break
        except Exception: pass
    def _testnachweis(self, pfad, dateien):
        """Jeder Fix braucht einen Nachweis: .py kompilieren/laufen lassen, .h statisch prüfen."""
        geprueft, fehler = 0, []
        for d in dateien[:8]:
            try:
                p = Path(pfad) / d
                if p.suffix.lower() == ".py":
                    r = BTEST.lauf("python_skript" if "test" not in p.name.lower() else "python_test",
                                   str(p), cwd=str(p.parent), timeout=120,
                                   log_ordner=str(WORKSPACE / "quassel-ki" / "logs"))
                    geprueft += 1
                    if not r.get("ok"):
                        fehler.append(f"{d}: {r.get('grund') or 'Exit ' + str(r.get('exit'))}")
                elif p.suffix.lower() == ".h":
                    txt = p.read_text(encoding="utf-8", errors="replace")
                    if "GENERATED_BODY()" not in txt and "class" in txt:
                        fehler.append(f"{d}: GENERATED_BODY() prüfen")
                    else:
                        geprueft += 1
                else:
                    geprueft += 1  # Doku/Config: Diff reicht
            except Exception as e:
                fehler.append(f"{d}: {e}")
        if fehler:
            return "FEHLER: " + "; ".join(fehler[:3])
        return f"{geprueft} Datei(en) geprüft, keine Befunde."
    def _hw_start(self):
        """v18: Hardware-Profil + Memory-Migration im Hintergrund (blockiert UI nie)."""
        try:
            if _HAT_QUASSEL_PAKET and (QCFG.get("hardware", {}) or {}).get("auto_detect", True):
                self.hw_profil = HW.profil()
                self.installierte_modelle = [m["name"] for m in self.hw_profil.get("modelle_installiert", [])]
                self.modell_groessen = {m["name"].lower(): m.get("gb", 0) for m in self.hw_profil.get("modelle_installiert", [])}
                self.hw_empfehlung = HW.empfehlung(self.hw_profil)
                self._ui(lambda: self.log("sys", "⚙️ " + self._hw_banner()))
        except Exception: pass
        try:
            if _HAT_QUASSEL_PAKET and (QCFG.get("memory", {}) or {}).get("enabled", True):
                MEM2.migrieren(str(MEMORY_PFAD), str(MEMORY2_PFAD))
                n_ep = MEM2.episoden_einfrieren(str(WORKSPACE / "quassel-ki" / "erinnerungen.json"), str(MEMORY2_PFAD))
                if n_ep: self._ui(lambda n=n_ep: self.log("sys", f"🧠 {n} alte Episoden als Fakten übernommen (Datei eingefroren)."))
                tage = int((QCFG.get("memory", {}) or {}).get("chat_archiv_tage", 30) or 0)
                if tage > 0:
                    n_ch = MEM2.chats_aufraeumen(str(CHATS_DIR), tage)
                    if n_ch: self._ui(lambda n=n_ch: self.log("sys", f"🗂 {n} alte Chats nach chats/archiv verschoben."))
        except Exception: pass
    def _hw_banner(self):
        """Verständliche Start-Konfiguration (Phase 2, Punkt 10). Nur echte Werte."""
        try:
            e, p = self.hw_empfehlung, self.hw_profil
            gpus = ", ".join(g.get("name", "?") for g in p.get("gpu", [])) or "keine GPU"
            modelle = ", ".join(self.installierte_modelle[:5]) or "keine"
            return (f"Hardware: {gpus} ({p.get('vram_gb', '?')} GB VRAM), {p.get('ram_total_gb', '?')} GB RAM. "
                f"Klasse {e.get('klasse', '?').upper()}: {e.get('beschreibung', '')} "
                f"Modelle: {modelle}. Keep-Alive {KEEP_ALIVE}, Chat-Tokens {CHAT_TOKENS}.")
        except Exception:
            return "Hardware-Check unvollständig."
    def _ctx_kuerzen(self):
        """v17: nicht hart abschneiden -> ältere Züge wandern in die Zusammenfassung."""
        try:
            self.history, self.zusammenfassung = verlauf_kuerzen(self.history, getattr(self, "zusammenfassung", "") or summary_laden())
            try: summary_speichern(self.zusammenfassung)
            except Exception: pass
            self._ctx_refresh()
        except Exception: pass
    def _auto_memory_lernen(self):
        """Merkt sich Fakten von allein (schnelles Modell im Hintergrund, stört nicht)."""
        try:
            if len(self.history) < 2: return
            schnipsel = "\n".join(f"{x.get('role')}: {x.get('content', '')[:400]}" for x in self.history[-2:])
            if len(schnipsel) < 60: return
        except Exception:
            return
        def _arbeit():
            try:
                proj = self._akt_projekt_name()
                for fakt in auto_fakten(schnipsel)[0]:
                    try:  # v20-Phase3: nur noch EIN System (memory2)
                        if _HAT_QUASSEL_PAKET:
                            MEM2.hinzufuegen(str(MEMORY2_PFAD), "fact", fakt,
                                             quelle="auto-memory", vertrauen=0.6, projekt=proj)
                        else:
                            memory_hinzu(fakt)
                    except Exception: pass
            except Exception: pass
        threading.Thread(target=_arbeit, daemon=True).start()
    def generierung_stoppen(self):
        if not self._generating: return
        self._gen_id += 1; self._generating = False
        try: self._agent_stop = True
        except Exception: pass
        self.sprecher.halt()
        try: self.send_btn.config(state="normal")
        except Exception: pass
        self.log("sys", "⏹ Generierung gestoppt.")
    # --- v19: Stumm / Quasseln-Stop / Agent-Stop / Global-Stop ---
    def _stumm_toggle(self):
        stumm = self.stumm_var.get()
        try: self.sprecher.stumm = stumm
        except Exception: pass
        if stumm:
            self.sprecher.halt()
            self.log("sys", "🔇 STUMM an: ich arbeite weiter, aber sage nichts mehr.")
        else:
            self.log("sys", "🔊 STUMM aus: ich spreche wieder.")
        self._zustand_refresh()
    def _talkstop_toggle(self):
        stop = self.talk_stop_var.get()
        self.log("sys", "🛑 Spontanes Reden AUS – Arbeit läuft weiter." if stop else "🛑 Quasseln-Stop aufgehoben.")
        self._zustand_refresh()
    def _jetzt_speichern(self):
        try:
            if self.history:
                (CHATS_DIR / "autosave.json").write_text(
                    json.dumps({"display": self.chat.get("1.0", "end-1c"), "history": self.history[-10:]}, ensure_ascii=False), encoding="utf-8")
        except Exception: pass
    def agent_stoppen(self):
        """Sauberer Agent-Stopp: keine neuen Tools, aktuellen Schritt beenden, Status sichern."""
        self._agent_stop = True
        self.finish_var.set(False)
        self._jetzt_speichern()
        self.log("sys", "⛔ AGENT ANGEHALTEN: keine neuen Tools mehr, Status gespeichert (autosave.json).")
        self._zustand_refresh()
    def alles_stoppen(self):
        """Globaler Not-Aus: alles anhalten, Stimme still, Schleifen aus, Status sichern."""
        self._agent_stop = True
        self._gen_id += 1; self._generating = False
        self.finish_var.set(False)
        try: self.autonom.set(False)
        except Exception: pass
        try: self.live_stopp("globaler Stopp")
        except Exception: pass
        self.sprecher.halt()
        self._jetzt_speichern()
        try: self.send_btn.config(state="normal")
        except Exception: pass
        self.log("sys", "⛔ STOP ALLES: Agent, Live, Stimme und autonome Schleifen angehalten. Status gespeichert. QUASSEL PAUSIERT.")
        self._zustand_refresh()
    def _zustand_refresh(self):
        try:
            if self.stumm_var.get(): zustand = "🔇 STUMM"
            elif self.talk_stop_var.get(): zustand = "🛑 REDEN GESTOPPT"
            else: zustand = "🟢 ONLINE 🔊 SPRICHT"
            zustand += " | 🤖 AUTONOM" if self.autonom.get() else " | 🤖 MANUELL"
            if self.finish_var.get(): zustand += " | 🚀 FIND&FINISH"
            if self.akt_projekt: zustand += f" | 📁 PROJEKT: {self.akt_projekt.name}"
            self.zustand_label.config(text=zustand)
        except Exception: pass
    def _busy_hint(self):
        try: self.status.config(text=f"{self.stimmung} | ⏳ bin dran – ⏹ Stopp oder warten")
        except Exception: pass
    def user_send(self):
        m = self.entry.get().strip()
        if not m: return
        if self._generating and not m.startswith(("/still", "/leise", "/clear", "/laut", "/stumm", "/agentstop", "/stopalles")):
            self._busy_hint(); return
        self.entry.delete(0, "end"); self._aktiv(); self.log("Du", m)
        if m.startswith("/"):
            self._befehl(m); return
        for name in re.findall(r"@([\w\-.]+)", m):  # @Datei erwähnen (Codex-@): hängt Treffer aus Index/Workspace an
            if not self._erwaehnung_anhaengen(name):
                self.log("sys", f"@{name} nicht gefunden (📇 Index bauen hilft).")
        self.history.append({"role": "user", "content": m})
        self._ctx_kuerzen()
        # PC-Kommandos in natürlicher Sprache (wie bisher)
        ml = m.lower()
        if any(w in ml for w in ["projekt finden", "finde projekt", "uproject suchen"]):
            self.projekte_finden(); return
        if "actor erstellen" in ml or "neue klasse" in ml:
            self.actor_dialog(); return
        if "check" in ml and "system" in ml:
            self.neuer_check(); return
        if "screenshot" in ml or "bildschirm foto" in ml or "mache ein foto" in ml:
            self.comp_shot(); return
        if any(w in ml for w in ["was siehst du", "schau auf den bildschirm", "siehst du", "bildschirm sehen"]):
            self.comp_sehen(); return
        if "maus" in ml and ("position" in ml or "wo ist" in ml or "zeig" in ml):
            self.comp_mauspos(); return
        if "klick" in ml:
            self.comp_klick(); return
        if "plugin installieren" in ml or "ue-plugin" in ml or "unreal-plugin" in ml:
            self.ue_plugin_dialog(); return
        if "schmiede" in ml or "neues spiel" in ml or "spiel erstellen" in ml:
            self.schmiede_start(); return
        if "forge" in ml or "gerüst" in ml or "geruest" in ml:
            self.forge_menue(); return
        if ml.startswith("commit") or "committe" in ml:
            self.git_commit_flow(); return
        if ml.startswith("skill ") or ml == "skill" or "führe skill" in ml or "fuhre skill" in ml:
            self.skill_ausfuehren(); return
        if ml.startswith("merk dir"):
            fakt = m[8:].strip()
            if not fakt:
                self.bot_sagt("Was soll ich mir merken? Schreib z.B. 'merk dir mein Projekt heißt ZombieRacer'."); return
            try:
                if _HAT_QUASSEL_PAKET:
                    MEM2.hinzufuegen(str(MEMORY2_PFAD), "user_preference", fakt,
                                     quelle="nutzer-direkt", vertrauen=1.0,
                                     projekt=self._akt_projekt_name(), wichtigkeit=5)
                else:
                    memory_hinzu(fakt)
            except Exception:
                memory_hinzu(fakt)
            self.history.pop()  # Kommando nicht in den Verlauf
            self.bot_sagt(f"Gemerk! '{fakt}' – vergesse ich nicht mehr. (🧠 zeigt alles)"); return
        if "vergiss" in ml and "alles" in ml:
            MEMORY_PFAD.write_text(json.dumps({"fakten": []}, ensure_ascii=False), encoding="utf-8")
            try:
                if _HAT_QUASSEL_PAKET:
                    MEM2.speichern(str(MEMORY2_PFAD), {"eintraege": []})
            except Exception: pass
            self.bot_sagt("Alles vergessen. Neuer Mensch, neues Glück."); return
        # Live-Modell fragen (Ask redet, Agent arbeitet), sonst Offline-Fallback
        if ollama_server_ok():
            self.live_ok = True; self._refresh_live_label()
            if self.modus.get() == "agent":
                threading.Thread(target=self._agent_arbeit, args=(m,), daemon=True).start()
            else:
                self._live_frage(list(self.history))
        else:
            self.live_ok = False; self._refresh_live_label()
            w = finde_wissen(m)
            if w: self.root.after(400, lambda: self.bot_sagt(w + " (Offline-Modus: Ollama gerade nicht erreichbar.)")); return
            self.root.after(600, lambda: self.bot_sagt("Ollama ist gerade nicht erreichbar – ich bin im Offline-Modus. Starte Ollama (ollama serve), dann rede ich wieder live über alles mit dir."))
    # --- Agent-Modus: arbeitet mit Werkzeugen statt nur zu reden ---
    def _permit_stufe(self):
        if self._god_an: return "voll"
        if self.pc_erlaubt.get(): return "auto"
        return "fragen"
    def _schreib_risiko(self, datei):
        """Phase 7: Impact vor jedem Schreiben. Schnell (Modul-Ordner), ohne Modell."""
        try:
            if not _HAT_QUASSEL_PAKET or not datei:
                return "UNKNOWN"
            r = IMP.datei_risiko(str(datei))
            if r:
                return r
            p = Path(str(datei))
            basis = p.parent if p.parent.is_dir() else None
            if not basis:
                return "UNKNOWN"
            stamm = re.sub(r"\W", "", p.stem)
            if not stamm:
                return "LOW"
            a = IMP.analysieren(str(basis), stamm, max_treffer=20)
            return a.get("risiko", "UNKNOWN")
        except Exception:
            return "UNKNOWN"
    def _tool_darf(self, tool, args):
        """True = ausführen. Fragt nach je nach Klasse + Permit-Stufe (aus Worker-Thread sicher)."""
        tname = tool.split("/", 1)[-1]
        stufe = self._permit_stufe()
        if tname in LESE_TOOLS or tname in (self.plugin_tools or {}):
            return True
        if tname in ("datei_schreiben", "text_ersetzen"):
            # Phase 7: Impact VOR allem anderen – HIGH/CRITICAL nie autonom schreiben
            risiko = self._schreib_risiko(str(args.get("datei", "")))
            if risiko in ("HIGH", "CRITICAL"):
                if stufe == "voll":
                    self._ui(lambda r=risiko: self.log("sys", f"⚠️ Impact {r} – schreibe trotzdem (Alles-Modus, deine Verantwortung)."))
                else:
                    self._ui(lambda r=risiko, t=tname: self.log("sys", f"🛡 Schreibschutz (Impact {r}): {t} verweigert. Ich mache Plan + Diff-Vorschlag statt zu schreiben."))
                    return False
        if stufe == "voll":
            return True
        vorschau = json.dumps(args, ensure_ascii=False)[:400]
        diff = ""
        if tname in ("datei_schreiben", "text_ersetzen"):
            try:
                pf = Path(str(args.get("datei", "")))
                alt_text = pf.read_text(encoding="utf-8", errors="replace") if pf.exists() else ""
                if tname == "datei_schreiben":
                    neu_text = str(args.get("inhalt", ""))
                else:
                    neu_text = alt_text.replace(str(args.get("alt", "")), str(args.get("neu", "")), 1) if str(args.get("alt", "")) in alt_text else alt_text
                diff = diff_bauen(alt_text, neu_text, pf.name)
                vorschau = f"{pf}\n--- Diff ---\n{diff[:1500]}"
            except Exception: pass
        if stufe == "auto" and tname in ("datei_schreiben", "text_ersetzen", "actor_erstellen_tool", "code_ausfuehren", "task_check", "doku_update"):
            try:
                ziel = str(args.get("datei", "") or args.get("ordner", "") or "")
                if ziel and self.pc._im_erlaubten_bereich(Path(ziel)):
                    self._ui(lambda: self.log("sys", f"✅ auto: {tname} {ziel[:80]}"))
                    return True
            except Exception: pass
        if diff and tname in ("datei_schreiben", "text_ersetzen"):
            return self._diff_fragen(f"Diff prüfen: {tname}", str(args.get("datei", "?")), diff)
        return self._frage_main("Agent-Aktion erlauben?",
            f"Werkzeug: {tname}\n{vorschau}\n\nAusführen? (Permit: {stufe} – /permit ändert das)")
    def _diff_fragen(self, titel, pfad, diff):
        """Diff-Vorschau im Fenster + Ja/Nein. Worker-sicher."""
        if threading.get_ident() == self._main_id:
            return self._diff_dialog(titel, pfad, diff)
        box, ev = {}, threading.Event()
        def _f():
            try: box["v"] = self._diff_dialog(titel, pfad, diff)
            except Exception: box["v"] = False
            ev.set()
        self._ui(_f)
        ev.wait(timeout=300)
        return box.get("v", False)
    def _diff_dialog(self, titel, pfad, diff):
        """Modales Diff-Fenster (läuft im Main-Thread)."""
        T = THEME
        box = {"v": False}
        top = tk.Toplevel(self.root)
        top.title(titel); top.geometry("640x480"); top.transient(self.root); top.grab_set()
        try: top.configure(bg=T["bg"])
        except Exception: pass
        tk.Label(top, text=str(pfad)[:100]).pack(anchor="w", padx=10, pady=(8, 0))
        txt = scrolledtext.ScrolledText(top, wrap="none", font=("Consolas", 9))
        txt.pack(fill="both", expand=True, padx=10, pady=6)
        try: txt.configure(bg=T["panel2"], fg=T["fg"], insertbackground=T["fg"])
        except Exception: pass
        txt.insert("end", diff[:8000]); txt.configure(state="disabled")
        row = tk.Frame(top); row.pack(pady=8)
        tk.Button(row, text="✅ Übernehmen", command=lambda: (box.update(v=True), top.destroy())).pack(side="left", padx=6)
        tk.Button(row, text="⛔ Abbrechen", command=top.destroy).pack(side="left", padx=6)
        self.root.wait_window(top)
        return box["v"]
    def _frage_main(self, titel, text):
        if threading.get_ident() == self._main_id:
            try: return messagebox.askyesno(titel, text)
            except Exception: return False
        box, ev = {}, threading.Event()
        def _f():
            try: box["v"] = messagebox.askyesno(titel, text)
            except Exception: box["v"] = False
            ev.set()
        self._ui(_f)
        ev.wait(timeout=300)
        return box.get("v", False)
    def _agent_parse(self, antwort):
        try:
            treffer = re.findall(r"```action\s*(\{.*?\})\s*```", antwort, re.S)
            aktionen = []
            for t in treffer:
                try:
                    obj = json.loads(t)
                    if isinstance(obj, dict) and "tool" in obj: aktionen.append(obj)
                except Exception: continue
            return aktionen
        except Exception: return []
    def _agent_text_ohne_aktionen(self, antwort):
        try: return re.sub(r"```action\s*\{.*?\}\s*```", "", antwort, flags=re.S).strip()
        except Exception: return antwort
    def _agent_arbeit(self, aufgabe):
        self.sprecher.halt(); self._generating = True; self._agent_stop = False
        self._gen_id += 1; self._gid = self._gen_id; self._gen_start = time.time()
        try: self.send_btn.config(state="disabled")
        except Exception: pass
        stufe = self._permit_stufe()
        sysmsg = ("Du bist im AGENT-Modus: du ARBEITEST, statt nur zu reden. "
            f"Werkzeuge ({AGENT_TOOLS}). Fordere sie so an (mehrere Blöcke ok):\n```action\n{{\"tool\": \"datei_lesen\", \"datei\": \"Pfad\"}}\n```\n"
            "Regeln: Erst lesen/auflisten, dann schreiben. Kleine Schritte. Argumente exakt (Pfade aus Anfrage/Index). "
            f"Permit-Stufe: {stufe} (schreiben fragt ggf. nach). Nach Tool-Ergebnissen weiter oder finale Antwort (ohne Block). Deutsch, locker.")
        verlauf = [{"role": "system", "content": sysmsg}]
        try: verlauf.append({"role": "system", "content": TONS.get(self.ton_var.get(), TONS["normal"])})
        except Exception: pass
        a_modell = None
        try:  # v18: Agent bekommt Coding-Modell + typisiertes Wissen
            a_modell, a_proto = self._router_modell(aufgabe)
            if not a_modell:
                rollen = ((QCFG.get("modelle", {}) or {}).get("rollen", {}) or None)
                a_modell = ROUTER.waehle_modell("coding", self.installierte_modelle or None, rollen, self._max_gb(), getattr(self, "modell_groessen", None)) if _HAT_QUASSEL_PAKET else None
            if a_modell:
                self._ui(lambda m=a_modell: self.log("sys", f"🧭 Agent-Modell: {m}"))
        except Exception:
            a_modell = None
        try:
            m2 = self._memory2_block(aufgabe)
            if m2: verlauf.append({"role": "system", "content": m2})
        except Exception: pass
        try:
            zf = getattr(self, "zusammenfassung", "") or summary_laden()
            if zf: verlauf.append({"role": "system", "content": "Früher im Chat (Zusammenfassung):\n" + zf})
        except Exception: pass
        try:
            alt_chat = chat_erinnerung_suchen(aufgabe)
            if alt_chat: verlauf.append({"role": "system", "content": "Ähnliches aus früheren Chats:\n" + alt_chat})
        except Exception: pass
        mem = memory_text()
        if mem: verlauf.append({"role": "system", "content": mem})
        verlauf += [dict(x) for x in self.history[-4:]]  # Kontext inkl. aktueller Aufgabe
        self._ui(lambda: self.log("sys", f"🤖 Agent startet (Permit: {stufe}, max 8 Runden, ⏹ = Stopp)"))
        runden, fertig_text, heil, max_runden = 0, "", [], 8
        while runden < max_runden and not self._agent_stop and self._gid == self._gen_id:
            runden += 1
            try:
                antwort = ollama_chat_once(verlauf, a_modell, 300, 600)
            except Exception as e:
                self._ui(lambda: self.log("sys", f"Agent-Fehler: {e}")); break
            if not antwort.strip():
                self._ui(lambda: self.log("sys", "Agent: leere Antwort, breche ab.")); break
            verlauf.append({"role": "assistant", "content": antwort[:3000]})
            aktionen = self._agent_parse(antwort)
            rest = self._agent_text_ohne_aktionen(antwort)
            if rest:
                self._ui(lambda t=rest: self.log("Agent", t[:1500]))
            if not aktionen:
                fertig_text = antwort; break
            for a in aktionen:
                if self._agent_stop or self._gid != self._gen_id: break
                tool, args = str(a.get("tool", "")), a.get("args", a)
                if not isinstance(args, dict): args = {}
                self._ui(lambda t=tool: self.log("sys", f"🔧 {t} …"))
                if not self._tool_darf(tool, args):
                    verlauf.append({"role": "user", "content": f"[Tool {tool} ABGELEHNT vom Nutzer]"})
                    self._ui(lambda t=tool: self.log("sys", f"⛔ {t} abgelehnt"))
                    continue
                erg = self.mcp.aufrufen(tool if "/" in tool else f"lokal/{tool}", args, self._mcp_ctx())
                self._ui(lambda t=tool, e=str(erg)[:200]: self.log("sys", f"🔧 {t} → {e}"))
                verlauf.append({"role": "user", "content": f"[Tool {tool} Ergebnis]\n{str(erg)[:3000]}"})
                try:  # Self-Healing merken: frisch geschriebene .py-Dateien später testen
                    tname = tool.split("/", 1)[-1]
                    ziel = str(args.get("datei", ""))
                    if tname in ("datei_schreiben", "text_ersetzen") and ziel.lower().endswith(".py") \
                       and str(erg).startswith(("Erstellt", "Ersetzt")) and ziel not in heil:
                        heil.append(ziel)
                except Exception: pass
            if self._agent_stop or self._gid != self._gen_id: break
            # Self-Healing: geschriebene .py-Dateien testen, Fehler -> 2 Reparatur-Runden
            if heil and max_runden == 8:
                self._ui(lambda: self.log("sys", f"🔧 Selbst-Heilung: teste {len(heil)} Datei(en)…"))
                fehler = []
                for datei in list(heil):
                    res = self.mcp.aufrufen("lokal/code_ausfuehren", {"datei": datei}, self._mcp_ctx())
                    self._ui(lambda d=datei, r=str(res)[:200]: self.log("sys", f"🧪 {Path(d).name} → {r}"))
                    if res.startswith("Exit 0"):
                        heil.remove(datei)
                    else:
                        fehler.append(f"Datei {datei}:\n{res[:1500]}")
                if fehler:
                    verlauf.append({"role": "user", "content":
                        "SELBST-TEST FEHLGESCHLAGEN:\n" + "\n".join(fehler) +
                        "\nRepariere mit text_ersetzen/datei_schreiben (genau 1-2 Aktionen), dann fertig melden."})
                    max_runden = runden + 2
                    self._ui(lambda: self.log("sys", "🔧 Reparatur-Runde (+2)…"))
        self._generating = False
        try: self.send_btn.config(state="normal")
        except Exception: pass
        self._ctx_refresh()
        if fertig_text:
            # Finale Antwort steht schon als Agent-Log -> nur vorlesen + Verlauf pflegen
            self.sprecher.sprich(fertig_text[:1500])
            self.history.append({"role": "assistant", "content": fertig_text[:1500]})
            self._ctx_kuerzen()
            try: self._auto_memory_lernen()
            except Exception: pass
            try:  # v18: Self-Check + Lesson nur wenn wirklich gearbeitet wurde
                spuren = [x.get("content", "") for x in verlauf
                          if x.get("role") == "user" and x.get("content", "").startswith("[Tool")]
                if spuren:
                    conf, risiko = self._self_check(aufgabe, spuren)
                    try: self._letzter_selfcheck = conf  # Phase 8: Finish-Loop wertet aus
                    except Exception: pass
                    if conf == "LOW":
                        self._ui(lambda r=risiko: self.bot_sagt(
                            "⚠️ Mein Selbst-Check ist unsicher" + (f": {r}" if r else "") +
                            " – prüfe das Ergebnis bitte gegen, bevor du es übernimmst."))
                    threading.Thread(target=self._lesson_speichern, args=(aufgabe, spuren, conf), daemon=True).start()
            except Exception: pass
            self.letzte_bot = time.time(); self.redelust = max(0, self.redelust - 25)
        elif not self._agent_stop:
            self.bot_sagt("Agent fertig – keine finale Antwort, schau ins Log oben. (max Runden oder Abbruch)")
    def _live_frage(self, verlauf):
        # Quassel-Stopp: während der Prompt läuft, kein autonomes Gequassel + keine alte Warteschlange
        self.sprecher.halt()
        self._generating = True
        # Kontext: Memory + Projektregeln + Anhänge + passender Skill vorne anstellen
        nachrichten = []
        mem = memory_text()
        if mem: nachrichten.append({"role": "system", "content": mem})
        try: nachrichten.append({"role": "system", "content": TONS.get(self.ton_var.get(), TONS["normal"])})
        except Exception: pass
        try:
            zf = getattr(self, "zusammenfassung", "") or summary_laden()
            if zf: nachrichten.append({"role": "system", "content": "Früher im Chat (Zusammenfassung):\n" + zf})
        except Exception: pass
        try:
            letzte_frage = next((x.get("content", "") for x in reversed(verlauf) if x.get("role") == "user"), "")
            alt_chat = chat_erinnerung_suchen(letzte_frage)
            if alt_chat: nachrichten.append({"role": "system", "content": "Ähnliches aus früheren Chats:\n" + alt_chat})
            m2 = self._memory2_block(letzte_frage)
            if m2: nachrichten.append({"role": "system", "content": m2})
        except Exception: pass
        try:  # quassel.md = AGENTS.md-Äquivalent (Projektregeln automatisch im Kontext)
            regeln = []
            for kandidat in [WORKSPACE / "quassel.md",
                             (self.akt_projekt.parent / "quassel.md") if self.akt_projekt else None]:
                if kandidat and kandidat.exists():
                    regeln.append(f"--- {kandidat} ---\n" + kandidat.read_text(encoding="utf-8", errors="replace")[:3000])
            if regeln:
                nachrichten.append({"role": "system", "content": "Projektregeln (quassel.md):\n" + "\n".join(regeln)})
        except Exception: pass
        try:
            letzte = next((x.get("content", "") for x in reversed(verlauf) if x.get("role") == "user"), "")
            sk = skill_finden(self.skills, letzte)
            if sk:
                nachrichten.append({"role": "system", "content":
                    f"Experten-Skill '{sk['name']}': {sk.get('beschreibung','')}\nVorgehen:\n{sk.get('anleitung','')}\n"
                    f"Nutze dieses Vorgehen für deine Antwort, bleib trotzdem locker und konkret."})
        except Exception: pass
        self._gen_id += 1; self._gid = self._gen_id; self._gen_start = time.time()
        if self.anhaenge:
            teile = []
            for a in self.anhaenge:
                inhalt, err = datei_text_lesen(a)
                teile.append(f"--- Datei {Path(a).name} ---\n" + (inhalt if inhalt else f"Fehler: {err}"))
            nachrichten.append({"role": "user", "content": "Angehängte Dateien:\n" + "\n".join(teile)[:14000]})
            self.anhaenge = []
            try: self.root.after(0, self._anhang_refresh)
            except Exception: pass
        nachrichten += verlauf
        try: self.send_btn.config(state="disabled")
        except Exception: pass
        try:  # v18 Brain-Router: Difficulty -> Rolle -> Modell (echte Entscheidung, geloggt)
            letzte_frage = next((x.get("content", "") for x in reversed(nachrichten) if x.get("role") == "user"), "")
            proto = {"schwere": "MEDIUM", "warum": "Fallback", "rolle": "?", "speed": self.speed_var.get()}
            r_modell, proto = self._router_modell(letzte_frage)
            if r_modell:
                modell, kurz = r_modell, {"fast": "⚡", "coding": "🧠", "reasoning": "🧠+", "vision": "👁", "fallback": "🛟"}.get(proto.get("rolle"), "🧠")
                self._ui(lambda p=proto, m=r_modell: self.log("sys", f"🧭 Router: {p['schwere']} ({p['warum']}) -> {p['rolle']} -> {m} [{p['speed']}]"))
            else:
                modell, kurz = route_modell(letzte_frage, self.route_var.get(), anhaenge_da=False)
        except Exception:
            modell, kurz = OLLAMA_MODEL, "🧠"
        self._letztes_modell = (modell, kurz)
        try:  # v18: adaptives Context-Budget aus Schwere + RAM statt fix 8192
            ram = (self.hw_profil or {}).get("ram_total_gb", 16) if self.hw_profil else 16
            self._letztes_ctx_budget = ROUTER.context_budget(proto.get("schwere", "MEDIUM"), ram, 19, self.speed_var.get(), ((QCFG.get("context", {}) or {}).get("budgets") if (QCFG.get("context", {}) or {}).get("adaptive", True) else {"TRIVIAL": NUM_CTX, "LOW": NUM_CTX, "MEDIUM": NUM_CTX, "HIGH": NUM_CTX, "MAX": NUM_CTX})) if _HAT_QUASSEL_PAKET else NUM_CTX
        except Exception:
            self._letztes_ctx_budget = NUM_CTX
        z = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"[{z}] ❯ Quassel-KI {kurz}:\n", "ki")
        self._stream_start = self.chat.index("end-1c")
        self.chat.configure(state="disabled"); self.chat.see("end")
        out_q, fertig = queue.Queue(), threading.Event()
        self._live_out, self._live_fertig, self._live_text = out_q, fertig, ""
        threading.Thread(target=ollama_stream, args=(nachrichten, out_q, fertig, modell, getattr(self, "_letztes_ctx_budget", NUM_CTX)), daemon=True).start()
        self.root.after(80, self._pump_stream)
    def _pump_stream(self):
        if self._gid != self._gen_id:  # gestoppt -> alte Tokens verwerfen
            self._generating = False
            try: self.send_btn.config(state="normal")
            except Exception: pass
            return
        try:
            while True:
                try: tok = self._live_out.get_nowait()
                except queue.Empty: break
                self._live_text += tok
                self.chat.configure(state="normal"); self.chat.insert("end", tok)
                self.chat.configure(state="disabled"); self.chat.see("end")
        except Exception: pass
        if self._live_fertig.is_set() and self._live_out.empty():
            try: self.chat.tag_add("ki_body", self._stream_start, self.chat.index("end-1c"))
            except Exception: pass
            self.chat.configure(state="normal"); self.chat.insert("end", "\n\n")
            self.chat.configure(state="disabled"); self.chat.see("end")
            try: self._tag_code(self._stream_start, self.chat.index("end-1c"))
            except Exception: pass
            try:
                dauer = time.time() - self._gen_start
                kurz = (self._letztes_modell[1] if self._letztes_modell else "")
                self.status.config(text=f"{self.stimmung} | {kurz} Antwort in {dauer:.0f}s")
            except Exception: pass
            self._ctx_refresh()
            try: self._auto_memory_lernen()
            except Exception: pass
            text = self._live_text.strip()
            if text:
                try:  # v19: STUMM gilt überall (kein Vorbeisprechen)
                    if not self.stumm_var.get():
                        self.sprecher.sprich(text)  # jede Live-Antwort wird vorgelesen
                except Exception:
                    try: self.sprecher.sprich(text)
                    except Exception: pass
                self.history.append({"role": "assistant", "content": text[:1500]})
                self._ctx_kuerzen()
            self.letzte_bot = time.time(); self.redelust = max(0, self.redelust - 25)
            self._generating = False
            try: self.send_btn.config(state="normal")
            except Exception: pass
            return
        self.root.after(80, self._pump_stream)

    # --- MCP ---
    def _mcp_autostart(self):
        cfg = self.mcp.config_laden()
        for name, scfg in cfg.get("servers", {}).items():
            if scfg.get("enabled"):
                self.mcp.server_starten(name, scfg)
        self._ui(self.mcp_refresh)
    def mcp_refresh(self):
        try:
            self.mcp_liste.delete(0, "end")
            for t in self.mcp.alle_tools(self.plugin_tools):
                self.mcp_liste.insert("end", t)
        except Exception: pass
    def _mcp_gewaehlt(self):
        try: return self.mcp_liste.get(self.mcp_liste.curselection()[0])
        except Exception: return None
    def _mcp_ctx(self):
        return {"pc": self.pc, "sysinfo": self.sysinfo, "projekt": self.akt_projekt,
                "plugintools": self.plugin_tools, "app": self}
    def mcp_run(self):
        tool = self._mcp_gewaehlt()
        if not tool:
            self.bot_sagt("Wähl erst ein MCP-Werkzeug aus der Liste."); return
        try: args = json.loads(self.mcp_params.get().strip() or "{}")
        except Exception: args = {}
        server = tool.split("/")[0]
        if server != "lokal" or tool.endswith(("datei_lesen", "code_ausfuehren", "projekt_index", "shell_befehl", "ue_plugin_installieren", "datei_schreiben", "text_ersetzen", "actor_erstellen_tool", "git_commit", "projekt_geruest", "klassen_batch", "asset_struktur", "task_check", "git_branch", "doku_update")) or server == "plugin":
            if not messagebox.askyesno("MCP ausführen?", f"Werkzeug '{tool}' mit {args} ausführen?"):
                return
        erg = self.mcp.aufrufen(tool, args, self._mcp_ctx())
        self.mcp_ergebnis = erg
        self.bot_sagt(f"MCP '{tool}' Ergebnis:\n{erg[:1500]}")
    def mcp_an_modell(self):
        if self._generating: self._busy_hint(); return
        tool = self._mcp_gewaehlt()
        if not tool:
            self.bot_sagt("Wähl erst ein MCP-Werkzeug aus."); return
        try: args = json.loads(self.mcp_params.get().strip() or "{}")
        except Exception: args = {}
        erg = self.mcp.aufrufen(tool, args, self._mcp_ctx())
        self.mcp_ergebnis = erg
        self.entry.delete(0, "end")
        self.entry.insert(0, f"Werkzeug {tool} meldet: {erg[:800]} – was bedeutet das, was soll ich tun?")
        self.user_send()

    def _stimme_wechsel(self, wahl):
        self.sprecher.stimme = STIMMEN.get(wahl, "de-DE-KatjaNeural")
        self.sprecher.backend = "windows" if self.sprecher.stimme == "windows" else ("edge" if (EDGE_OK and PYGAME_OK) else "windows")

    # --- Sehen + Handeln (Quassel-Fähigkeit bleibt aktiv, pausiert nur bei Generierung) ---
    def comp_shot(self):
        pf, err = screenshot_machen()
        if err:
            self.bot_sagt(f"Screenshot geht nicht: {err}"); return
        self.log("Quassel-KI", f"Screenshot: {pf}")
        self.sprecher.sprich("Schau mal, so sehe ich deinen Bildschirm gerade.")
        try:
            from PIL import Image, ImageTk
            top = tk.Toplevel(self.root); top.title(str(pf.name))
            img = Image.open(pf); img.thumbnail((640, 640))
            tkimg = ImageTk.PhotoImage(img)
            tk.Label(top, image=tkimg).pack()
            top._ref = tkimg  # gegen GC
        except Exception: pass
    def comp_sehen(self):
        if self._generating: self._busy_hint(); return
        frage = self.entry.get().strip() or "Was ist auf dem Bildschirm zu sehen und was sollte ich als Nächstes tun?"
        self.entry.delete(0, "end"); self._aktiv()
        self.log("Du", f"[blickt auf Bildschirm] {frage}")
        self.sprecher.halt(); self._generating = True
        def _arbeit():
            pf, err = screenshot_machen()
            if err:
                self._ui(lambda: (setattr(self, "_generating", False), self.bot_sagt(f"Sehen geht nicht: {err}"))); return
            try:
                # Vision-Modell versteht Englisch am besten -> danach antwortet quassel-ki auf Deutsch
                beschreibung = bild_sehen("Describe this screenshot in detail: active windows, texts, buttons, what is happening.", pf)
            except Exception as e:
                self._ui(lambda: (setattr(self, "_generating", False), self.bot_sagt(f"Vision-Modell ({VISION_MODEL}) nicht bereit: {e}. Hole es mit: ollama pull moondream"))); return
            self._ui(lambda: self._sehen_fertig(frage, beschreibung))
        threading.Thread(target=_arbeit, daemon=True).start()
    def _erwaehnung_anhaengen(self, name):
        """Sucht Datei im Index/Workspace. True wenn angehängt."""
        kandidaten = []
        try:
            if INDEX_PFAD.exists():
                idx = json.loads(INDEX_PFAD.read_text(encoding="utf-8")).get("dateien", [])
                kandidaten = [t["pfad"] for t in idx if name.lower() in t["pfad"].lower()]
        except Exception: pass
        if not kandidaten:
            try:
                for f in WORKSPACE.rglob(f"*{name}*"):
                    if f.is_file() and f.stat().st_size < 200000:
                        kandidaten.append(str(f))
                    if len(kandidaten) >= 3: break
            except Exception: pass
        if not kandidaten: return False
        self.anhaenge.append(kandidaten[0]); self._anhang_refresh()
        return True
    def _sehen_fertig(self, frage, beschreibung):
        self.history.append({"role": "user", "content": f"[Bildschirmbeschreibung per Vision: {beschreibung[:1200]}] Nutzerfrage dazu: {frage}. Antworte auf Deutsch, frech und hilfreich."})
        self._ctx_kuerzen()
        self._generating = False
        self._live_frage(list(self.history))
    def comp_mauspos(self):
        if not PYAUTO_OK:
            self.bot_sagt("Maus-Steuerung fehlt: pip install pyautogui"); return
        x, y = _pag.position()
        self.bot_sagt(f"Meine Maus ist gerade bei x={x}, y={y}. Sag mir Koordinaten und ich klicke dort – aber nur nach deiner Bestätigung. (Failsafe: Maus in die Bildschirm-Ecke = Stopp)")
    def comp_klick(self):
        if not PYAUTO_OK:
            self.bot_sagt("Maus-Steuerung fehlt: pip install pyautogui"); return
        ko = simpledialog.askstring("Klicken", "Wohin? Format: x,y  (z.B. 800,450). Tipp: erst 'Maus-Pos' zum Kalibrieren.", parent=self.root)
        if not ko: return
        try: x, y = [int(v) for v in ko.replace(" ", "").split(",")]
        except Exception:
            self.bot_sagt("Das habe ich nicht verstanden. Format: x,y – z.B. 800,450."); return
        if not messagebox.askyesno("Wirklich klicken?", f"Soll ich bei x={x}, y={y} linksklicken?"):
            self.log("Quassel-KI", "(Klick abgebrochen.)"); return
        threading.Thread(target=lambda: (_pag.moveTo(x, y, duration=0.4), _pag.click()), daemon=True).start()
        self.bot_sagt(f"Geklickt bei {x},{y}. Ich quassle natürlich weiter.")
    def comp_schreiben(self):
        if not PYAUTO_OK:
            self.bot_sagt("Maus-Steuerung fehlt: pip install pyautogui"); return
        txt = simpledialog.askstring("Text schreiben", "Welchen Text soll ich tippen? (Feld vorher anklicken!)", parent=self.root)
        if not txt: return
        if not messagebox.askyesno("Wirklich tippen?", f"Diesen Text tippen?\n{txt[:200]}"):
            return
        threading.Thread(target=lambda: _pag.write(txt, interval=0.02), daemon=True).start()
        self.bot_sagt("Getippt. Weiter geht's.")

    # --- GPT-Features: Anhang, Memory, Index ---
    def _anhang_refresh(self):
        try:
            n = len(self.anhaenge)
            self.anhang_label.config(text="kein Anhang" if not n else f"📎 {n} Datei(en): " + ", ".join(Path(a).name for a in self.anhaenge[-2:]))
        except Exception: pass
    def datei_anhaengen(self):
        pf = filedialog.askopenfilename(title="Datei anhängen (Code/Text, max 200KB)",
            filetypes=[("Code/Text", "*.h *.cpp *.cs *.py *.ini *.json *.txt *.md *.uproject"), ("Alle", "*.*")])
        if not pf: return
        try:
            if Path(pf).stat().st_size > 200000:
                self.bot_sagt("Datei zu groß (>200KB). Nimm einen Ausschnitt."); return
        except Exception as e:
            self.bot_sagt(f"Geht nicht: {e}"); return
        self.anhaenge.append(pf); self._anhang_refresh()
        self.bot_sagt(f"Angehängt: {Path(pf).name}. Stell jetzt deine Frage dazu – ich lese die Datei mit.")
    def memory_zeigen(self):
        # v20-Phase3: einheitliches typisiertes Memory (memory2.json ist die Wahrheit)
        try:
            if _HAT_QUASSEL_PAKET:
                weg = MEM2.bereinigen(str(MEMORY2_PFAD))
                daten = MEM2.laden(str(MEMORY2_PFAD))["eintraege"]
                if weg: self.log("sys", f"🧠 {weg} abgelaufene Erinnerungen aufgeräumt.")
                if not daten:
                    self.bot_sagt("Noch nichts gemerkt – ich lerne beim Reden automatisch dazu."); return
                txt = "\n".join(f"• [{e.get('type')}] {e.get('content','')[:90]}"
                                f"{' [' + e['projekt'] + ']' if e.get('projekt') else ''}"
                                f" (W{e.get('wichtigkeit', 3)}, {e.get('confidence', '?')})" for e in daten[-15:])
                self.bot_sagt(f"Mein Gedächtnis ({len(daten)} Einträge):\n{txt}")
                return
        except Exception: pass
        fakten = memory_laden().get("fakten", [])
        txt = "Noch nichts gemerkt. Sag 'merk dir ...'." if not fakten else "\n".join(f"• {f}" for f in fakten)
        if fakten and messagebox.askyesno("Memory", f"Gemerkte Fakten:\n{txt}\n\nAlles vergessen?"):
            MEMORY_PFAD.write_text(json.dumps({"fakten": []}, ensure_ascii=False), encoding="utf-8")
            self.bot_sagt("Memory gelöscht. Wer bist du überhaupt?")
        else:
            self.bot_sagt(f"Mein Gedächtnis:\n{txt}")
    def index_bauen(self):
        basis = self.akt_projekt.parent if self.akt_projekt else None
        if not basis:
            basis = filedialog.askdirectory(title="Unreal-Projektordner wählen")
            if not basis: return
        self.bot_sagt("Scanne Projekt...")
        def _arbeit():
            try:
                treffer = projekt_index_bauen(basis)
                self._ui(lambda: self.bot_sagt(f"Index fertig: {len(treffer)} Dateien. Frag z.B. 'was macht HealthComponent?' und hänge die Datei per 📎 an."))
            except Exception as e:
                self._ui(lambda: self.bot_sagt(f"Index-Fehler: {e}"))
        threading.Thread(target=_arbeit, daemon=True).start()

    # --- Alles-Modus + Skills + Unreal-Installer ---
    def godmode_toggle(self):
        if self.godmode.get():
            code = simpledialog.askstring("Alles-Modus", "Wirklich? Tippe ALLES zur Bestätigung.\n(Zugriff überall außer System-Ordnern, Shell-Befehle, alles mit Nachfrage + Blockliste + Log)", parent=self.root)
            if code != "ALLES":
                self.godmode.set(False); return
            self.pc.unbegrenzt = True
            self._god_an = True
            try: self.god_banner.config(text="🔓 ALLES-MODUS AN – erweitert, mit Nachfrage + Blockliste + aktionen.log", fg="red")
            except Exception: pass
            self.pc.aktion_loggen("ALLES-MODUS aktiviert")
            self.bot_sagt("Alles-Modus AN. Ich kann jetzt überall hin (außer System-Ordner) + Shell. Aber: jede Aktion fragt dich, Blockliste + Log laufen. Mit Vorsicht!")
        else:
            if not self._god_an: return
            self._god_an = False
            self.pc.unbegrenzt = False
            try: self.god_banner.config(text="")
            except Exception: pass
            self.pc.aktion_loggen("ALLES-MODUS deaktiviert")
            self.bot_sagt("Alles-Modus aus. Wieder brav in den Projekt-Ordnern.")
    def skills_neu_laden(self):
        self.skills = skills_laden()
        try:
            menü = self.skill_menü["menu"]; menü.delete(0, "end")
            for s in [x.get("name", "?") for x in self.skills]:
                menü.add_command(label=s, command=lambda v=s: self.skill_var.set(v))
        except Exception: pass
        self.bot_sagt(f"{len(self.skills)} Skills geladen: " + ", ".join(s.get('name', '?') for s in self.skills))
    def skill_ausfuehren(self, name=None):
        name = name or self.skill_var.get()
        s = next((x for x in self.skills if x.get("name") == name), None)
        if not s:
            s = skill_finden(self.skills, self.entry.get())
            if not s:
                self.bot_sagt("Kein Skill gewählt/gepasst. Wähl einen aus der Liste."); return
        fokus = simpledialog.askstring("Skill: " + s["name"], "Worum geht's genau? (Leer = nur Anleitung, Text = maßgeschneiderte Antwort vom Modell)", parent=self.root)
        if fokus and fokus.strip() and ollama_server_ok():
            self._aktiv(); self.log("Du", f"[Skill {s['name']}] {fokus.strip()}")
            self.history.append({"role": "user", "content": f"[Skill {s['name']}] {fokus.strip()}"})
            self._ctx_kuerzen()
            self.live_ok = True; self._refresh_live_label()
            self._live_frage(list(self.history))  # Skill wird automatisch als Playbook injiziert
            return
        self.log("Du", f"[Skill: {s['name']}]")
        self.bot_sagt(f"Skill '{s['name']}': {s.get('beschreibung','')}\n{s.get('anleitung','')}")
    def ue_plugin_dialog(self):
        self.ue_plugin_installieren(
            filedialog.askdirectory(title="Unreal-Projektordner (mit .uproject) wählen") if not self.akt_projekt else str(self.akt_projekt.parent),
            simpledialog.askstring("Plugin-Name", "Name (z.B. MeinPlugin):", parent=self.root) or "")
    def ue_plugin_installieren(self, projekt_ordner, name, _mit_nachfrage=True):
        """Echter Unreal-Plugin-Installer: .uplugin + Modul + Beispielklasse + .uproject-Eintrag."""
        name = re.sub(r'\W', '', name or "")
        if not name or not projekt_ordner or not Path(projekt_ordner).exists():
            msg = "Abgebrochen: Projektordner + Name nötig."
            self.bot_sagt(msg); return msg
        if not self.pc._im_erlaubten_bereich(Path(projekt_ordner)) and not self.pc.unbegrenzt:
            msg = "Projektordner außerhalb der erlaubten Bereiche (oder 🔓 Alles-Modus)."
            self.bot_sagt(msg); return msg
        pname = name[0].upper() + name[1:]
        plug = Path(projekt_ordner) / "Plugins" / pname
        dateien = {
            plug / f"{pname}.uplugin": json.dumps({"FileVersion": 3, "Version": 1, "VersionName": "1.0",
                "FriendlyName": pname, "Description": "Mit Quassel-KI erstellt.", "Category": "Quassel",
                "CreatedBy": "Quassel-KI", "Modules": [{"Name": pname, "Type": "Runtime", "LoadingPhase": "Default"}]}, indent=2),
            plug / "Source" / pname / f"{pname}.Build.cs": (
                f"using UnrealBuildTool;\npublic class {pname} : ModuleRules\n{{\n"
                f"\tpublic {pname}(ReadOnlyTargetRules Target) : base(Target)\n\t{{\n"
                f"\t\tPCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;\n"
                f"\t\tPublicDependencyModuleNames.AddRange(new string[] {{ \"Core\", \"CoreUObject\", \"Engine\" }});\n\t}}\n}}\n"),
            plug / "Source" / pname / "Public" / f"{pname}Actor.h": (
                f"#pragma once\n#include \"CoreMinimal.h\"\n#include \"GameFramework/Actor.h\"\n#include \"{pname}Actor.generated.h\"\n"
                f"UCLASS()\nclass A{pname}Actor : public AActor\n{{\n\tGENERATED_BODY()\npublic:\n\tA{pname}Actor();\n"
                f"\tUPROPERTY(EditAnywhere, BlueprintReadWrite, Category=\"{pname}\")\n\tfloat Power = 1.f;\nprotected:\n"
                f"\tvirtual void BeginPlay() override;\n}};\n"),
            plug / "Source" / pname / "Private" / f"{pname}Actor.cpp": (
                f"#include \"{pname}Actor.h\"\nA{pname}Actor::A{pname}Actor() {{ PrimaryActorTick.bCanEverTick = false; }}\n"
                f"void A{pname}Actor::BeginPlay() {{ Super::BeginPlay(); UE_LOG(LogTemp, Warning, TEXT(\"{pname} aktiv!\")); }}\n"),
            plug / "Source" / pname / "Private" / f"{pname}.cpp": (
                f"#include \"Modules/ModuleManager.h\"\nIMPLEMENT_PRIMARY_GAME_MODULE(FDefaultGameModuleImpl, {pname}, \"{pname}\");\n"),
        }
        liste = "\n".join("• " + str(p.relative_to(projekt_ordner)) for p in dateien)
        if _mit_nachfrage and not messagebox.askyesno("Plugin installieren?", f"Plugin '{pname}' in\n{projekt_ordner}\n\n{liste}\n\n.uproject wird ergänzt. Weiter?"):
            self.log("Quassel-KI", "(Installer abgebrochen.)"); return "Abgebrochen."
        try:
            for p, inhalt in dateien.items():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(inhalt, encoding="utf-8")
            uprojects = list(Path(projekt_ordner).glob("*.uproject"))
            if uprojects:
                uj = json.loads(uprojects[0].read_text(encoding="utf-8"))
                plugs = uj.setdefault("Plugins", [])
                if not any(x.get("Name") == pname for x in plugs):
                    plugs.append({"Name": pname, "Enabled": True})
                    uprojects[0].write_text(json.dumps(uj, indent=4), encoding="utf-8")
            self.pc.aktion_loggen(f"ue_plugin_installiert {pname} in {projekt_ordner}")
            msg = f"Plugin '{pname}' installiert ({len(dateien)} Dateien) + in .uproject aktiviert. In UE: Projekt neu generieren (Generate Visual Studio Files) + kompilieren."
            self.bot_sagt(msg); return msg
        except Exception as e:
            msg = f"Installer-Fehler: {e}"
            self.bot_sagt(msg); return msg

    # --- Spiel-Schmiede: aus Idee wird Unreal-Projekt (GDD + Tasks + Klassen) ---
    def schmiede_start(self):
        idee = simpledialog.askstring("Spiel-Schmiede", "Deine Spielidee in 1-3 Sätzen:", parent=self.root)
        if not idee or not idee.strip(): return
        name = simpledialog.askstring("Spiel-Schmiede", "Spielname (Ordner):", parent=self.root) or "MeinSpiel"
        safe = re.sub(r'\W+', '', name)[:30] or "MeinSpiel"
        if self._generating: self._busy_hint(); return
        self._aktiv(); self.log("Du", f"[Schmiede] {safe}: {idee.strip()}")
        self.sprecher.halt(); self._generating = True
        try: self.send_btn.config(state="disabled")
        except Exception: pass
        threading.Thread(target=self._schmiede_arbeit, args=(safe, idee.strip()), daemon=True).start()
    def _schmiede_arbeit(self, safe, idee):
        ordner = WORKSPACE / "quassel-ki" / "spiele" / safe
        try: ordner.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._ui(lambda: (setattr(self, "_generating", False), self.bot_sagt(f"Ordner geht nicht: {e}")))
            self._ui(lambda: self.send_btn.config(state="normal"))
            return
        self._ui(lambda: self.bot_sagt(f"Schmiede läuft für '{safe}' (3 Schritte, dauert ein paar Minuten – ich melde mich)..."))
        kontext = (f"Hardware: {self.sysinfo['cpu']} Kerne, {self.sysinfo['ram']}GB RAM, {self.sysinfo['gpu']}. "
                   f"Unreal: {list(self.sysinfo['editors'].keys()) or 'UE 5.x'}. Antworte auf Deutsch, kompakt, mit Markdown-##-Überschriften.")
        schritte = [
            ("konzept", f"Spielidee: {idee}\n{kontext}\nTeil 1 KONZEPT: ## Titel ## Pitch (2 Sätze) ## Säulen (3) ## Core Loop (1 Satz) ## Scope-Warnung (zu groß? was streichen?)."),
            ("systeme", f"Spielidee: {idee}\n{kontext}\nTeil 2 SYSTEME+KLASSEN: ## Systeme (Player, Gegner, UI, Save, Audio – je 3 Zeilen) ## C++-Klassen (Name, erbt von, 3 Member, UCLASS-Regeln beachten)."),
            ("aufgaben", f"Spielidee: {idee}\n{kontext}\nTeil 3 AUFGABEN: ## Phasen (Prototyp, Juice, Content, Menü/Save, Test, Release – je 3 Aufgaben mit Haken - [ ]) ## Git-Plan (Branches) ## Playtest-Fragen (3)."),
        ]
        teile = {}
        for key, prompt in schritte:
            try:
                teile[key] = ollama_chat_once([{"role": "system", "content": memory_text()},
                                               {"role": "user", "content": prompt}])
            except Exception as e:
                teile[key] = f"(Fehler bei {key}: {e})"
            if not ollama_server_ok():
                self._ui(lambda: (setattr(self, "_generating", False), self.bot_sagt("Ollama weggebrochen – Schmiede abgebrochen.")))
                return
        try:
            (ordner / "GDD.md").write_text(f"# {safe}\nIdee: {idee}\n\n" + teile["konzept"] + "\n\n" + teile["systeme"] + "\n\n" + teile["aufgaben"], encoding="utf-8")
            (ordner / "klassen.md").write_text(teile["systeme"], encoding="utf-8")
            (ordner / "tasks.md").write_text(teile["aufgaben"], encoding="utf-8")
            self.history.append({"role": "user", "content": f"[Schmiede {safe}] {idee}"})
            self._ctx_kuerzen()
        except Exception as e:
            self._ui(lambda: (setattr(self, "_generating", False), self.bot_sagt(f"Speichern geht nicht: {e}"))); return
        def _fertig():
            self._generating = False
            try: self.send_btn.config(state="normal")
            except Exception: pass
            self._ctx_refresh()
            self.bot_sagt(f"Geschmiedet! '{safe}' liegt in spiele/{safe}/: GDD.md, klassen.md, tasks.md. Nächster Schritt: Prototyp mit 1 Mechanik (Graybox). Frag mich dazu!")
            try:
                if messagebox.askyesno("Schmiede+", f"Unreal-Gerüst für '{safe}' gleich mitbauen? (.uproject + Source + Content-Struktur in neuem Ordner)"):
                    ziel = filedialog.askdirectory(title="Wohin mit dem Unreal-Projekt? (leerer Ordner)")
                    if ziel:
                        self.bot_sagt(self.mcp.aufrufen("lokal/projekt_geruest", {"projekt_ordner": ziel, "spielname": safe}, self._mcp_ctx()))
                        self.bot_sagt(self.mcp.aufrufen("lokal/asset_struktur", {"projekt_ordner": ziel}, self._mcp_ctx()))
            except Exception: pass
        self._ui(_fertig)

    # --- Forge-Menü (10-Punkte-Workflow zum Anklicken) ---
    def forge_menue(self):
        wahl = (simpledialog.askstring("Forge", "1 Gerüst  2 Klassen-Batch  3 Assets  4 Tasks  5 Log-Check  6 Impact\nNummer:", parent=self.root) or "").strip()
        if wahl == "1": self.forge_geruest_dialog()
        elif wahl == "2": self.forge_klassen_dialog()
        elif wahl == "3":
            o = filedialog.askdirectory(title="Unreal-Projektordner")
            if o: self.bot_sagt(self.mcp.aufrufen("lokal/asset_struktur", {"projekt_ordner": o}, self._mcp_ctx()))
        elif wahl == "4":
            s = simpledialog.askstring("Tasks", "Spielname (spiele-Ordner):", parent=self.root)
            if s: self.bot_sagt(self.mcp.aufrufen("lokal/tasks_status", {"spiel": s}, self._mcp_ctx()))
        elif wahl == "5":
            o = str(self.akt_projekt.parent) if self.akt_projekt else filedialog.askdirectory(title="Unreal-Projektordner")
            if o: self.bot_sagt(self.mcp.aufrufen("lokal/log_analyse", {"projekt_ordner": o}, self._mcp_ctx()))
        elif wahl == "6":
            o = simpledialog.askstring("Impact", "Code-Ordner:", parent=self.root)
            k = simpledialog.askstring("Impact", "Klassenname (z.B. AHealthPickup):", parent=self.root)
            if o and k: self.bot_sagt(self.mcp.aufrufen("lokal/impact_check", {"ordner": o, "klasse": k}, self._mcp_ctx()))
    def forge_geruest_dialog(self):
        o = filedialog.askdirectory(title="Wohin mit dem Projekt? (leerer Ordner)")
        n = simpledialog.askstring("Gerüst", "Spielname:", parent=self.root)
        if o and n:
            self.bot_sagt(self.mcp.aufrufen("lokal/projekt_geruest", {"projekt_ordner": o, "spielname": n}, self._mcp_ctx()))
    def forge_klassen_dialog(self):
        o = filedialog.askdirectory(title="Source-Ordner (z.B. .../Source/MeinSpiel/)")
        raw = simpledialog.askstring("Klassen-Batch", "Format: Name:Eltern,Name:Eltern\nEltern: Actor Pawn Character Component GameMode PlayerController SaveGame Object\nz.B. HealthPickup:Actor,EnemyAI:Character", parent=self.root)
        if not (o and raw): return
        klassen = []
        for teil in raw.split(","):
            if ":" in teil:
                n, e = teil.split(":", 1)
                klassen.append({"name": n.strip(), "eltern": e.strip() or "Actor", "member": []})
        if klassen:
            self.bot_sagt(self.mcp.aufrufen("lokal/klassen_batch", {"ordner": o, "klassen": klassen}, self._mcp_ctx()))

    # --- PC / Unreal Aktionen (immer mit Nachfrage!) ---
    def _darf(self):
        if not self.pc_erlaubt.get():
            self.bot_sagt("PC-Aktionen sind aus. Hake oben 'PC-Aktionen erlauben' an – ich frage trotzdem vor jedem Schritt nach. Sicherheit zuerst.")
            return False
        return True
    def neuer_check(self):
        self.sysinfo = system_check()
        self.bot_sagt(f"Neuer Check: {self.sysinfo['profil']}, RAM {self.sysinfo['ram']}GB, frei {self.sysinfo['disk_free']}GB. {self.sysinfo['empfehlung']}")
    def projekte_finden(self):
        projs = self.pc.finde_projekte()
        if not projs:
            self.bot_sagt("Keine .uproject gefunden in Documents/Workspace. Sag mir den Ordner, oder erstelle ein Projekt in UE 5.8 (Third Person Template zum Lernen).")
            return
        self.akt_projekt = projs[0]
        txt = "Gefunden:\n" + "\n".join(f"• {p}" for p in projs[:5])
        info = self.pc.lese_uproject(self.akt_projekt)
        txt += f"\nAktives Projekt: {self.akt_projekt.name} (Engine: {info.get('EngineAssociation', '?')})"
        self.bot_sagt(txt)
    def projekt_oeffnen(self):
        if not self._darf(): return
        if not self.akt_projekt:
            self.projekte_finden()
            if not self.akt_projekt: return
        eds = self.sysinfo["editors"]
        if not eds:
            self.bot_sagt("Kein UnrealEditor gefunden. Installiere UE über Epic Launcher."); return
        # passende Version wählen, sonst neueste
        info = self.pc.lese_uproject(self.akt_projekt)
        ver = str(info.get("EngineAssociation", "")).strip("{} ")
        exe = eds.get(ver, list(eds.values())[-1])
        if not messagebox.askyesno("Wirklich starten?", f"Unreal starten?\nEditor: {exe}\nProjekt: {self.akt_projekt}\nDas dauert 1-3 Min und frisst RAM."):
            self.log("Quassel-KI", "(Start abgebrochen – deine Entscheidung.)"); return
        try:
            self.pc.projekt_starten(self.akt_projekt, exe)
            self.bot_sagt(f"Starte {self.akt_projekt.name} mit UE {ver or '?'}... Gib ihm Zeit. Bei deiner A1000: Scalability erstmal auf Medium lassen!")
        except Exception as e:
            self.bot_sagt(f"Start fehlgeschlagen: {e}")
    def actor_dialog(self):
        if not self._darf(): return
        name = simpledialog.askstring("C++ Actor", "Klassenname (z.B. HealthPickup):", parent=self.root)
        if not name: return
        ziel = filedialog.askdirectory(title="Quell-Ordner wählen (z.B. .../Source/DeinGame/)", initialdir=str(WORKSPACE))
        if not ziel: return
        zp = Path(ziel)
        if not self.pc._im_erlaubten_bereich(zp):
            # trotzdem erlauben nach extra Nachfrage, aber warnen
            if not messagebox.askyesno("Außerhalb?", f"{zp} liegt außerhalb meiner Standard-Ordner. Trotzdem dort schreiben?"):
                return
        if not messagebox.askyesno("Dateien schreiben?", f"Schreibe {name}.h + {name}.cpp nach\n{zp}?"):
            return
        try:
            h, cpp = self.pc.actor_erstellen(zp, name)
            self.bot_sagt(f"Fertig! {h.name} + {cpp.name} erstellt. In UE: Tools → Refresh Visual Studio Project, dann kompilieren. Denk an UPROPERTY für den Editor!")
        except Exception as e:
            self.bot_sagt(f"Fehler beim Schreiben: {e}")

    def _bock_loop(self):
        # Pausiert solange ein Prompt ausgeführt wird (Quassel-Stopp bei Generierung)
        # v19: STUMM und QUASSELN-STOP unterdrücken alles Spontane (Arbeit läuft weiter)
        if self.autonom.get() and not self._generating and not self.stumm_var.get() and not self.talk_stop_var.get():
            jetzt = time.time(); stille = jetzt - self.letzte_user; seit = jetzt - self.letzte_bot
            tol = self.stille_toleranz.get(); bock = self.bock_level.get()
            if stille > tol: self.redelust += (bock/100)*8 + 2
            elif stille > tol/2: self.redelust += (bock/100)*3
            self.redelust = min(100, self.redelust)
            self.bock_meter.config(text=f"Redelust {int(self.redelust)}% (still {int(stille)}s)")
            self.status.config(text=f"{self.stimmung} | {self.sysinfo['profil']}")
            if self.redelust > 80 and seit > 12:
                msg = random.choice(UNREAL_TIPPS + CODING_TIPPS) if (self.training.get() and random.random() < 0.7) else random.choice(["Ey, noch da? Frag mich was zu Unreal!", "Mir ist langweilig – soll ich Projekte suchen? Schreib 'Projekte finden'."])
                self.bot_sagt(msg)
        self.root.after(1000, self._bock_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = QuasselKI(root)
    try: root.mainloop()
    finally:
        try: app.sprecher.stop()
        except: pass
        try: app.mcp.stoppen()
        except: pass
