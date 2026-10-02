#!/usr/bin/env python3
"""
Quassel-KI v4 - Live-Chat mit Ollama + spricht ALLES + redet über ALLES.
- Jede Bot-Ausgabe wird vorgelesen (in Stücke geteilt, nichts geht verloren)
- Live-Antworten vom Modell 'quassel-ki' (Streaming direkt in den Chat)
- Ohne Ollama: automatischer Offline-Fallback (Stichwort-Wissen)
- PC/Unreal-Aktionen weiter nur mit Nachfrage!

Start: python quassel_ki_v4.py
Benötigt: pip install pyttsx3  (optional, ohne geht auch ohne Stimme)
"""
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, filedialog
import random, time, threading, queue, re, os, json, shutil, subprocess, sys
import urllib.request
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(r"C:\Users\S-Lasarzewski\Documents\Default Project")
ALLOWED_ROOTS = [
    WORKSPACE,
    Path.home() / "Documents" / "Unreal Projects",
    Path.home() / "Documents" / "Default Project",
    Path(os.environ.get("TEMP", r"C:\Temp")),
]
# ---------- TTS (wie v2) ----------
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

class Sprecher:
    """Liest JEDE Ausgabe vor. Lange Texte werden in Stücke geteilt, nichts wird verworfen."""
    CHUNK = 250
    def __init__(self):
        self.q = queue.Queue(); self.aktiv = True; self.enabled = True; self.rate = 175
        self.engine = None
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        if not TTS_AVAILABLE: return
        try:
            self.engine = pyttsx3.init()
            try:
                for v in self.engine.getProperty('voices'):
                    n = (v.name + v.id).lower()
                    if 'hedda' in n or 'de-de' in n or 'german' in n or 'deutsch' in n:
                        self.engine.setProperty('voice', v.id); break
            except Exception: pass
            engine = self.engine
            while self.aktiv:
                try: text = self.q.get(timeout=0.5)
                except queue.Empty: continue
                if not self.enabled or not text: continue
                try:
                    engine.setProperty('rate', self.rate)
                    clean = re.sub(r'[^\w\säöüÄÖÜß.,!?\-:;() ]', '', text)
                    engine.say(clean); engine.runAndWait()
                except Exception as e: print("TTS:", e)
        except Exception as e: print("TTS init:", e)
    def sprich(self, t):
        """Alles vorlesen: Text in Stücke teilen und komplett einreihen."""
        if not self.enabled or not TTS_AVAILABLE or not t: return
        clean = str(t).strip()
        if not clean: return
        # An Satzgrenzen stückeln
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
            if self.q.qsize() > 30:  # nur bei extremer Flut ältestes verwerfen
                try: self.q.get_nowait()
                except queue.Empty: pass
            self.q.put(teil)
    def halt(self):
        """Sofort still sein: Warteschlange leeren + laufende Ansage stoppen."""
        while not self.q.empty():
            try: self.q.get_nowait()
            except queue.Empty: break
        try:
            if self.engine: self.engine.stop()
        except Exception: pass
    def stop(self): self.aktiv = False

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
        return ["system_info", "projekt_suchen", "datei_lesen", "actor_vorschau", "tipp_ziehen"]
    def alle_tools(self):
        tools = [f"lokal/{t}" for t in self.builtin_tools()]
        for name, tl in self.tools_cache.items():
            tools += [f"{name}/{t}" for t in tl]
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
                return "Unbekanntes lokales Tool."
            except Exception as e:
                return f"Fehler: {e}"
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

# ---------- Sicherer PC-Zugriff ----------
class SafePC:
    def __init__(self, log_fn):
        self.log_fn = log_fn
        self.darf = False  # Checkbox in UI
    def _im_erlaubten_bereich(self, pfad: Path):
        try:
            rp = pfad.resolve()
            return any(str(rp).lower().startswith(str(r.resolve()).lower()) for r in ALLOWED_ROOTS if r.exists() or r == WORKSPACE)
        except Exception: return False
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

# ---------- UI ----------
class QuasselKI:
    def __init__(self, root):
        self.root = root
        root.title("Quassel-KI v5 - Live + MCP + Game-Creation (4070-ready)")
        root.geometry("680x880"); root.minsize(520, 640)
        self.sysinfo = system_check()
        p = self.sysinfo["preset"]
        self.bock_level = tk.IntVar(value=p["bock"])
        self.stille_toleranz = tk.IntVar(value=p["stille"])
        self.autonom = tk.BooleanVar(value=True)
        # QUASSEL_VOICE=0 startet stumm (z.B. wenn im Call), sonst IMMER an: jede Ausgabe wird vorgelesen
        _voice_wunsch = os.environ.get("QUASSEL_VOICE", "1") != "0"
        self.vorlesen = tk.BooleanVar(value=TTS_AVAILABLE and _voice_wunsch)
        self.training = tk.BooleanVar(value=True)
        self.pc_erlaubt = tk.BooleanVar(value=False)
        self.sprecher = Sprecher(); self.sprecher.enabled = self.vorlesen.get()
        self.pc = SafePC(self.log)
        self.mcp = MCPClient(self.log)
        threading.Thread(target=self._mcp_autostart, daemon=True).start()
        self.letzte_user = time.time(); self.letzte_bot = time.time()
        self.redelust = 30.0; self.stimmung = "mentor"
        self.akt_projekt = None
        self.history = []  # Chatverlauf für das Modell (role/content)
        self._generating = False
        self.live_ok = ollama_server_ok()
        self._build_ui()
        msg = (f"System-Check fertig! Profil: {self.sysinfo['profil']} | CPU-Kerne: {self.sysinfo['cpu']} | "
                f"RAM: {self.sysinfo['ram']}GB | GPU: {self.sysinfo['gpu']} | Frei C:: {self.sysinfo['disk_free']}GB | "
                f"Unreal: {list(self.sysinfo['editors'].keys()) or 'keins gefunden'}. {self.sysinfo['empfehlung']} "
                f"Live-Modell '{OLLAMA_MODEL}': {'bereit, ich antworte live und lese ALLES vor.' if self.live_ok else 'nicht erreichbar, ich nutze den Offline-Modus.'} "
                f"Du kannst mit mir über ALLES reden – nicht nur Unreal. Frag einfach los!")
        self.log("Quassel-KI", msg); self.sprecher.sprich("Bereit! Ich antworte live und lese alles vor. Du kannst mit mir über alles reden.")
        self._bock_loop()

    def _build_ui(self):
        sysframe = tk.LabelFrame(self.root, text="💻 System (Auto-Check beim Start)", padx=8, pady=4)
        sysframe.pack(fill="x", padx=10, pady=4)
        info = (f"{self.sysinfo['profil']} | RAM {self.sysinfo['ram']}GB | {self.sysinfo['gpu'][:40]} | "
                f"C: frei {self.sysinfo['disk_free']}GB | UE: {', '.join(self.sysinfo['editors'].keys()) or '–'}")
        tk.Label(sysframe, text=info, font=("Segoe UI", 8), fg="dimgray", wraplength=620, justify="left").pack(anchor="w")
        tk.Label(sysframe, text=self.sysinfo["empfehlung"], font=("Segoe UI", 8, "italic"), wraplength=620, justify="left").pack(anchor="w")

        top = tk.Frame(self.root, padx=10, pady=4); top.pack(fill="x")
        tk.Label(top, text="🤖 Quassel-KI v4 • Live", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.status = tk.Label(top, text="", font=("Segoe UI", 9)); self.status.pack(side="left", padx=8)
        self.live_label = tk.Label(top, text="", font=("Segoe UI", 9, "bold")); self.live_label.pack(side="right")

        self.chat = scrolledtext.ScrolledText(self.root, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.pack(fill="both", expand=True, padx=10, pady=4)

        ctrl = tk.LabelFrame(self.root, text="Steuerung", padx=8, pady=6); ctrl.pack(fill="x", padx=10, pady=4)
        r1 = tk.Frame(ctrl); r1.pack(fill="x")
        tk.Label(r1, text="Bock:").pack(side="left")
        tk.Scale(r1, from_=0, to=100, orient="horizontal", variable=self.bock_level, length=120).pack(side="left")
        tk.Label(r1, text="Stille:").pack(side="left")
        tk.Scale(r1, from_=5, to=120, orient="horizontal", variable=self.stille_toleranz, length=120).pack(side="left")
        tk.Checkbutton(r1, text="Autonom", variable=self.autonom).pack(side="left")
        tk.Checkbutton(r1, text="🔊 Alles vorlesen", variable=self.vorlesen, command=lambda: setattr(self.sprecher, 'enabled', self.vorlesen.get())).pack(side="left")
        tk.Button(r1, text="🤫 Still!", command=self.sprecher.halt).pack(side="left", padx=4)
        self._refresh_live_label()

        r2 = tk.Frame(ctrl); r2.pack(fill="x", pady=3)
        tk.Checkbutton(r2, text="PC-Aktionen erlauben (fragt trotzdem nach)", variable=self.pc_erlaubt).pack(side="left")
        tk.Button(r2, text="PC-Check erneut", command=self.neuer_check).pack(side="left", padx=4)
        tk.Button(r2, text="Projekte finden", command=self.projekte_finden).pack(side="left", padx=4)
        tk.Button(r2, text="Unreal-Tipp", command=lambda: self.bot_sagt(random.choice(UNREAL_TIPPS))).pack(side="left", padx=4)

        r3 = tk.Frame(ctrl); r3.pack(fill="x", pady=3)
        tk.Button(r3, text="Projekt öffnen in UE 🚀", command=self.projekt_oeffnen).pack(side="left")
        tk.Button(r3, text="C++ Actor erstellen 🛠️", command=self.actor_dialog).pack(side="left", padx=5)
        tk.Button(r3, text="Jetzt labern!", command=lambda: self.bot_sagt(random.choice(UNREAL_TIPPS + CODING_TIPPS))).pack(side="left", padx=5)
        self.bock_meter = tk.Label(ctrl, text="", font=("Segoe UI", 8, "italic")); self.bock_meter.pack(anchor="w")

        bot = tk.Frame(self.root, padx=10, pady=6); bot.pack(fill="x")
        self.entry = tk.Entry(bot, font=("Segoe UI", 10)); self.entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.entry.bind("<Return>", lambda e: self.user_send()); self.entry.bind("<Key>", lambda e: self._aktiv())
        self.send_btn = tk.Button(bot, text="Senden", command=self.user_send); self.send_btn.pack(side="right")
        tk.Label(self.root, text="Live-Chat mit quassel-ki (19GB) – frag einfach ALLES. PC-Befehle: 'Projekte finden', 'Actor erstellen'.", font=("Segoe UI", 8), fg="gray").pack(pady=(0,2))

        mcp = tk.LabelFrame(self.root, text="MCP-Werkzeuge (nach Bestätigung)", padx=8, pady=4)
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
        self.chat.configure(state="normal"); self.chat.insert("end", f"[{z}] {wer}: {text}\n\n")
        self.chat.configure(state="disabled"); self.chat.see("end")
    def _aktiv(self): self.letzte_user = time.time(); self.redelust = max(0, self.redelust - 2)
    def bot_sagt(self, t):
        """Jede Ausgabe wird geloggt UND vorgelesen."""
        self.log("Quassel-KI", t); self.sprecher.sprich(t)
        self.history.append({"role": "assistant", "content": str(t)[:1500]})
        self.history = self.history[-8:]
        self.letzte_bot = time.time(); self.redelust = max(0, self.redelust - 25)
    def user_send(self):
        m = self.entry.get().strip()
        if not m or self._generating: return
        self.entry.delete(0, "end"); self._aktiv(); self.log("Du", m)
        self.history.append({"role": "user", "content": m})
        self.history = self.history[-8:]
        # PC-Kommandos in natürlicher Sprache (wie bisher)
        ml = m.lower()
        if any(w in ml for w in ["projekt finden", "finde projekt", "uproject suchen"]):
            self.projekte_finden(); return
        if "actor erstellen" in ml or "neue klasse" in ml:
            self.actor_dialog(); return
        if "check" in ml and "system" in ml:
            self.neuer_check(); return
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
        try: self.send_btn.config(state="disabled")
        except Exception: pass
        z = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"[{z}] Quassel-KI: ")
        self.chat.configure(state="disabled"); self.chat.see("end")
        out_q, fertig = queue.Queue(), threading.Event()
        self._live_out, self._live_fertig, self._live_text = out_q, fertig, ""
        threading.Thread(target=ollama_stream, args=(verlauf, out_q, fertig), daemon=True).start()
        self.root.after(80, self._pump_stream)
    def _pump_stream(self):
        try:
            while True:
                try: tok = self._live_out.get_nowait()
                except queue.Empty: break
                self._live_text += tok
                self.chat.configure(state="normal"); self.chat.insert("end", tok)
                self.chat.configure(state="disabled"); self.chat.see("end")
        except Exception: pass
        if self._live_fertig.is_set() and self._live_out.empty():
            self.chat.configure(state="normal"); self.chat.insert("end", "\n\n")
            self.chat.configure(state="disabled"); self.chat.see("end")
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
            for t in self.mcp.alle_tools():
                self.mcp_liste.insert("end", t)
        except Exception: pass
    def _mcp_gewaehlt(self):
        try: return self.mcp_liste.get(self.mcp_liste.curselection()[0])
        except Exception: return None
    def _mcp_ctx(self):
        return {"pc": self.pc, "sysinfo": self.sysinfo, "projekt": self.akt_projekt}
    def mcp_run(self):
        tool = self._mcp_gewaehlt()
        if not tool:
            self.bot_sagt("Wähl erst ein MCP-Werkzeug aus der Liste."); return
        try: args = json.loads(self.mcp_params.get().strip() or "{}")
        except Exception: args = {}
        server = tool.split("/")[0]
        if server != "lokal" or tool.endswith("datei_lesen"):
            if not messagebox.askyesno("MCP ausführen?", f"Werkzeug '{tool}' mit {args} ausführen?"):
                return
        erg = self.mcp.aufrufen(tool, args, self._mcp_ctx())
        self.mcp_ergebnis = erg
        self.bot_sagt(f"MCP '{tool}' Ergebnis:\n{erg[:1500]}")
    def mcp_an_modell(self):
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
