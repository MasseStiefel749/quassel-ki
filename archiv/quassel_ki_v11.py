#!/usr/bin/env python3
"""
Quassel-KI v11 - Codex-Look mit Ansichten (Chat/Tools/Agent), Live-Agent, Sessions.
Start: python quassel_ki_v11.py
"""
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, filedialog
import random, time, threading, queue, re, os, json, shutil, subprocess, sys
import urllib.request, asyncio, tempfile, base64
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
    payload = json.dumps({"model": VISION_MODEL, "prompt": frage, "stream": False, "images": [data]}).encode()
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

def ollama_server_ok(timeout=3):
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False

def ollama_stream(messages, out_q, fertig):
    """Fragt das Modell im Stream. Tokens -> out_q (str), am Ende fertig.set(). Fehler -> out_q.put('[FEHLER]...')."""
    try:
        data = json.dumps({"model": OLLAMA_MODEL, "messages": messages, "stream": True}).encode()
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

def ollama_chat_once(messages, modell=None, timeout=300):
    """Einmalige Antwort ohne Stream (für Agent + Reviews)."""
    data = json.dumps({"model": modell or OLLAMA_MODEL, "messages": messages, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode()).get("response", "")

AGENT_MODEL = os.environ.get("QUASSEL_AGENT", "llama3.1")  # schnell+klein für Live-Schritte
LIVE_SYS = ("Du steuerst den PC des Nutzers im Live-Modus (ausdrücklich genehmigt). "
    "Du bekommst pro Runde: Aufgabe, Bildschirmbeschreibung (Bild ist 1280px breit), Mausposition. "
    "Antworte mit GENAU EINEM Aktionsblock:\n```action\n{\"tool\": \"click\", \"x\": 800, \"y\": 450}\n```\n"
    "Tools: click(x,y im 1280er-Bild), type(text), key(name wie enter, tab, esc), wait(sekunden 1-5), "
    "say(kurze Meldung an Nutzer), done(Ergebnis-Zusammenfassung). "
    "Ohne Aktionsblock = nur kurze Statusmeldung (max 2 Sätze). Genau 1 Aktion pro Antwort. "
    "Nie raten bei Passwörtern/Zahlungen: dann say + done. Antworte auf Deutsch.")

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
                "projekt_index", "code_ausfuehren", "shell_befehl", "ue_plugin_installieren"]
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
    "/help": "Befehle: /neu /clear /still /laut /leise /shot /sehen /maus /memory /index /tipp /modell /ctx /skill /plugin /god /export /permit /status /review",
    "/neu": None, "/clear": None, "/still": None, "/laut": None, "/leise": None,
    "/shot": None, "/sehen": None, "/maus": None, "/memory": None,
    "/index": None, "/tipp": None, "/modell": None, "/ctx": None,
    "/skill": None, "/plugin": None, "/god": None, "/export": None,
    "/permit": "Lesen|Auto|Voll – /permit voll schaltet Alles-Modus (mit ALLES-Code)",
    "/status": "Status: Modell, Kontext, Modus, Stimme, Live",
    "/review": "Code-Review: erst Datei per 📎 oder @Name anhängen, dann /review",
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
        root.title("❯ quassel-codex v11")
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
        self.training = tk.BooleanVar(value=True)
        self.pc_erlaubt = tk.BooleanVar(value=False)
        self.sprecher = Sprecher(); self.sprecher.enabled = self.vorlesen.get()
        self.pc = SafePC(self.log)
        self.mcp = MCPClient(self.log)
        threading.Thread(target=self._mcp_autostart, daemon=True).start()
        self.skills = skills_laden()
        self.plugin_tools, self.plugin_buttons = plugins_laden(self)
        self.godmode = tk.BooleanVar(value=False)
        self.letzte_user = time.time(); self.letzte_bot = time.time()
        self.redelust = 30.0; self.stimmung = "mentor"
        self.akt_projekt = None
        self.history = []  # Chatverlauf für das Modell (role/content)
        self._generating = False
        self._gen_id = 0  # Antwort-Stopp: alte Generationen werden verworfen
        self._gen_start = 0.0
        self._god_an = False
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
                    json.dumps({"display": self.chat.get("1.0", "end-1c"), "history": self.history[-8:]}, ensure_ascii=False), encoding="utf-8")
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
                         ("💾 Export", self.chat_exportieren)]:
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
        self.btn_agent = tk.Button(top, text="🤖 Agent", command=lambda: self._ansicht("agent")); self.btn_agent.pack(side="left", padx=2)
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
        self.ctx_label.pack(side="right", padx=8)
        tk.Label(bar, text="❯ /help für Befehle", bg=THEME["panel"], fg=THEME["muted"], font=("Consolas", 8)).pack(side="left", padx=8)
        self._ctx_refresh()
        self._chats_refresh()

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
        try: self.ctx_label.config(text=f"ctx {len(self.history)}/8 • {OLLAMA_MODEL} • Bock {self.bock_level.get()}%")
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
        self.chat.configure(state="normal"); self.chat.delete("1.0", "end"); self.chat.configure(state="disabled")
        self._chats_refresh(); self._ctx_refresh()
        self.bot_sagt("Neuer Chat. Alter Kram ist in der Sidebar gespeichert.")
    def _chat_laden(self):
        if self._generating: self._busy_hint(); return
        try: key = self.chat_liste.get(self.chat_liste.curselection()[0])
        except Exception: return
        try:
            obj = json.loads((CHATS_DIR / f"{key}.json").read_text(encoding="utf-8"))
            self.history = obj.get("history", [])[-8:]
            self.chat.configure(state="normal"); self.chat.delete("1.0", "end")
            self.chat.insert("end", obj.get("display", "")); self.chat.configure(state="disabled")
            self._tag_code("1.0", "end"); self.chat.see("end"); self._ctx_refresh()
        except Exception: pass
    # --- Ansichten + Live-Agent (sieht Bildschirm, steuert Maus/Tastatur nach Freigabe) ---
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
        try: self.root.after(0, self._live_banner_update)
        except Exception: pass
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
                    antwort = ollama_chat_once(verlauf, AGENT_MODEL)
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
            self.bot_sagt(f"Modell: {OLLAMA_MODEL} (19B qwen-coder) + Vision: {VISION_MODEL}. Lokal, offline-fähig."); return True
        if cmd == "/ctx":
            self.bot_sagt(f"Kontext: {len(self.history)}/8 Nachrichten. Memory: {len(memory_laden().get('fakten', []))} Fakten."); return True
        if cmd == "/skill": self.skill_ausfuehren(); return True
        if cmd == "/plugin": self.ue_plugin_dialog(); return True
        if cmd == "/god":
            self.godmode.set(not self.godmode.get()); self.godmode_toggle(); return True
        if cmd == "/export": self.chat_exportieren(); return True
        if cmd == "/status":
            modus = "🔓 VOLL (Alles)" if self._god_an else ("🟡 AUTO (PC erlaubt)" if self.pc_erlaubt.get() else "🟢 LESEN (Nachfrage)")
            stimme = self.stimme_var.get() if self.vorlesen.get() else "aus"
            self.bot_sagt(f"❯ Status: Modell {OLLAMA_MODEL} + {AGENT_MODEL}(Agent) + {VISION_MODEL}(Augen) | ctx {len(self.history)}/8 | Modus {modus} | Stimme {stimme} | Live {'AN' if self._live_an else 'aus'} | Skills {len(self.skills)} | Chats {len(list(CHATS_DIR.glob('*.json')))}")
            return True
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
            self.history = self.history[-8:]; self._ctx_refresh()
            if ollama_server_ok(): self._live_frage(list(self.history))
            else: self.bot_sagt("Offline – Review braucht das Live-Modell.")
            return True
        if cmd.startswith("/"):
            self.bot_sagt(f"Unbekannt: {cmd}. /help zeigt alle."); return True
        return False
    def _aktiv(self): self.letzte_user = time.time(); self.redelust = max(0, self.redelust - 2)
    def bot_sagt(self, t):
        """Jede Ausgabe wird geloggt UND vorgelesen."""
        self.log("Quassel-KI", t); self.sprecher.sprich(t)
        self.history.append({"role": "assistant", "content": str(t)[:1500]})
        self.history = self.history[-8:]; self._ctx_refresh()
        self.letzte_bot = time.time(); self.redelust = max(0, self.redelust - 25)
    def generierung_stoppen(self):
        if not self._generating: return
        self._gen_id += 1; self._generating = False
        self.sprecher.halt()
        try: self.send_btn.config(state="normal")
        except Exception: pass
        self.log("sys", "⏹ Generierung gestoppt.")
    def _busy_hint(self):
        try: self.status.config(text=f"{self.stimmung} | ⏳ bin dran – ⏹ Stopp oder warten")
        except Exception: pass
    def user_send(self):
        m = self.entry.get().strip()
        if not m: return
        if self._generating and not m.startswith(("/still", "/leise", "/clear", "/laut")):
            self._busy_hint(); return
        self.entry.delete(0, "end"); self._aktiv(); self.log("Du", m)
        if m.startswith("/"):
            self._befehl(m); return
        for name in re.findall(r"@([\w\-.]+)", m):  # @Datei erwähnen (Codex-@): hängt Treffer aus Index/Workspace an
            if not self._erwaehnung_anhaengen(name):
                self.log("sys", f"@{name} nicht gefunden (📇 Index bauen hilft).")
        self.history.append({"role": "user", "content": m})
        self.history = self.history[-8:]; self._ctx_refresh()
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
        if ml.startswith("skill ") or ml == "skill" or "führe skill" in ml or "fuhre skill" in ml:
            self.skill_ausfuehren(); return
        if ml.startswith("merk dir"):
            fakt = m[8:].strip()
            if not fakt:
                self.bot_sagt("Was soll ich mir merken? Schreib z.B. 'merk dir mein Projekt heißt ZombieRacer'."); return
            memory_hinzu(fakt)
            self.history.pop()  # Kommando nicht in den Verlauf
            self.bot_sagt(f"Gemerk! '{fakt}' – vergesse ich nicht mehr. (🧠 zeigt alles)"); return
        if "vergiss" in ml and "alles" in ml:
            MEMORY_PFAD.write_text(json.dumps({"fakten": []}, ensure_ascii=False), encoding="utf-8")
            self.bot_sagt("Alles vergessen. Neuer Mensch, neues Glück."); return
        # Live-Modell fragen, sonst Offline-Fallback
        if ollama_server_ok():
            self.live_ok = True; self._refresh_live_label()
            self._live_frage(list(self.history))
        else:
            self.live_ok = False; self._refresh_live_label()
            w = finde_wissen(m)
            if w: self.root.after(400, lambda: self.bot_sagt(w + " (Offline-Modus: Ollama gerade nicht erreichbar.)")); return
            self.root.after(600, lambda: self.bot_sagt("Ollama ist gerade nicht erreichbar – ich bin im Offline-Modus. Starte Ollama (ollama serve), dann rede ich wieder live über alles mit dir."))
    def _live_frage(self, verlauf):
        # Quassel-Stopp: während der Prompt läuft, kein autonomes Gequassel + keine alte Warteschlange
        self.sprecher.halt()
        self._generating = True
        # Kontext: Memory + Projektregeln + Anhänge + passender Skill vorne anstellen
        nachrichten = []
        mem = memory_text()
        if mem: nachrichten.append({"role": "system", "content": mem})
        try:  # quassel.md = AGENTS.md-Äquivalent (Projektregeln automatisch im Kontext)
            regeln = []
            for kandidat in [WORKSPACE / "quassel.md",
                             (self.akt_projekt.parent / "quassel.md") if self.akt_projekt else None]:
                if kandidat and kandidat.exists():
                    regeln.append(f"--- {kandid} ---\n" + kandidat.read_text(encoding="utf-8", errors="replace")[:3000])
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
        z = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"[{z}] ❯ Quassel-KI:\n", "ki")
        self._stream_start = self.chat.index("end-1c")
        self.chat.configure(state="disabled"); self.chat.see("end")
        out_q, fertig = queue.Queue(), threading.Event()
        self._live_out, self._live_fertig, self._live_text = out_q, fertig, ""
        threading.Thread(target=ollama_stream, args=(nachrichten, out_q, fertig), daemon=True).start()
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
                self.status.config(text=f"{self.stimmung} | Antwort in {dauer:.0f}s")
            except Exception: pass
            self._ctx_refresh()
            text = self._live_text.strip()
            if text:
                self.sprecher.sprich(text)  # jede Live-Antwort wird vorgelesen
                self.history.append({"role": "assistant", "content": text[:1500]})
                self.history = self.history[-8:]
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
        self.root.after(0, self.mcp_refresh)
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
        if server != "lokal" or tool.endswith(("datei_lesen", "code_ausfuehren", "projekt_index", "shell_befehl", "ue_plugin_installieren")) or server == "plugin":
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
                self.root.after(0, lambda: (setattr(self, "_generating", False), self.bot_sagt(f"Sehen geht nicht: {err}"))); return
            try:
                # Vision-Modell versteht Englisch am besten -> danach antwortet quassel-ki auf Deutsch
                beschreibung = bild_sehen("Describe this screenshot in detail: active windows, texts, buttons, what is happening.", pf)
            except Exception as e:
                self.root.after(0, lambda: (setattr(self, "_generating", False), self.bot_sagt(f"Vision-Modell ({VISION_MODEL}) nicht bereit: {e}. Hole es mit: ollama pull moondream"))); return
            self.root.after(0, lambda: self._sehen_fertig(frage, beschreibung))
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
        self.history = self.history[-8:]
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
                self.root.after(0, lambda: self.bot_sagt(f"Index fertig: {len(treffer)} Dateien. Frag z.B. 'was macht HealthComponent?' und hänge die Datei per 📎 an."))
            except Exception as e:
                self.root.after(0, lambda: self.bot_sagt(f"Index-Fehler: {e}"))
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
            self.history = self.history[-8:]; self._ctx_refresh()
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
        if self.autonom.get() and not self._generating:
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
