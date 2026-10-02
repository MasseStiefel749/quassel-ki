#!/usr/bin/env python3
"""
Quassel-KI v3 - mit System-Check + kontrolliertem PC/Unreal-Zugriff.
KEIN blinder Vollzugriff: jede Schreib-/Start-Aktion fragt nach + loggt.

Start: python quassel_ki_v3.py
Benötigt: pip install pyttsx3  (optional, ohne geht auch ohne Stimme)
"""
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, filedialog
import random, time, threading, queue, re, os, json, shutil, subprocess, sys
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
    def __init__(self):
        self.q = queue.Queue(); self.aktiv = True; self.enabled = True; self.rate = 175
        threading.Thread(target=self._loop, daemon=True).start()
    def _loop(self):
        if not TTS_AVAILABLE: return
        try:
            engine = pyttsx3.init()
            try:
                for v in engine.getProperty('voices'):
                    n = (v.name + v.id).lower()
                    if 'hedda' in n or 'de-de' in n or 'german' in n or 'deutsch' in n:
                        engine.setProperty('voice', v.id); break
            except Exception: pass
            while self.aktiv:
                try: text = self.q.get(timeout=0.5)
                except queue.Empty: continue
                if not self.enabled or not text: continue
                try:
                    engine.setProperty('rate', self.rate)
                    clean = re.sub(r'[^\w\säöüÄÖÜß.,!?\-:;() ]', '', text)[:280]
                    engine.say(clean); engine.runAndWait()
                except Exception as e: print("TTS:", e)
        except Exception as e: print("TTS init:", e)
    def sprich(self, t):
        if self.enabled and TTS_AVAILABLE:
            while self.q.qsize() > 2:
                try: self.q.get_nowait()
                except queue.Empty: break
            self.q.put(t)
    def stop(self): self.aktiv = False

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
        root.title("Quassel-KI v3 - System-Check + PC/Unreal-Helfer")
        root.geometry("680x760"); root.minsize(520, 620)
        self.sysinfo = system_check()
        p = self.sysinfo["preset"]
        self.bock_level = tk.IntVar(value=p["bock"])
        self.stille_toleranz = tk.IntVar(value=p["stille"])
        self.autonom = tk.BooleanVar(value=True)
        # QUASSEL_VOICE=0 startet stumm (z.B. wenn im Call), sonst Sprachausgabe an
        _voice_wunsch = os.environ.get("QUASSEL_VOICE", "1") != "0"
        self.vorlesen = tk.BooleanVar(value=p["tts_an"] and TTS_AVAILABLE and _voice_wunsch)
        self.training = tk.BooleanVar(value=True)
        self.pc_erlaubt = tk.BooleanVar(value=False)
        self.sprecher = Sprecher(); self.sprecher.enabled = self.vorlesen.get()
        self.pc = SafePC(self.log)
        self.letzte_user = time.time(); self.letzte_bot = time.time()
        self.redelust = 30.0; self.stimmung = "mentor"
        self.akt_projekt = None
        self._build_ui()
        msg = (f"System-Check fertig! Profil: {self.sysinfo['profil']} | CPU-Kerne: {self.sysinfo['cpu']} | "
               f"RAM: {self.sysinfo['ram']}GB | GPU: {self.sysinfo['gpu']} | Frei C:: {self.sysinfo['disk_free']}GB | "
               f"Unreal: {list(self.sysinfo['editors'].keys()) or 'keins gefunden'}. {self.sysinfo['empfehlung']} "
               f"Ich passe mich an: Bock={p['bock']}, Stille={p['stille']}s. Frag mich zu Unreal, oder nutz die PC-Buttons – ich frage immer vorher!")
        self.log("Quassel-KI", msg); self.sprecher.sprich("System Check fertig. Ich habe mich an deinen Rechner angepasst.")
        self._bock_loop()

    def _build_ui(self):
        sysframe = tk.LabelFrame(self.root, text="💻 System (Auto-Check beim Start)", padx=8, pady=4)
        sysframe.pack(fill="x", padx=10, pady=4)
        info = (f"{self.sysinfo['profil']} | RAM {self.sysinfo['ram']}GB | {self.sysinfo['gpu'][:40]} | "
                f"C: frei {self.sysinfo['disk_free']}GB | UE: {', '.join(self.sysinfo['editors'].keys()) or '–'}")
        tk.Label(sysframe, text=info, font=("Segoe UI", 8), fg="dimgray", wraplength=620, justify="left").pack(anchor="w")
        tk.Label(sysframe, text=self.sysinfo["empfehlung"], font=("Segoe UI", 8, "italic"), wraplength=620, justify="left").pack(anchor="w")

        top = tk.Frame(self.root, padx=10, pady=4); top.pack(fill="x")
        tk.Label(top, text="🤖 Quassel-KI v3", font=("Segoe UI", 13, "bold")).pack(side="left")
        self.status = tk.Label(top, text="", font=("Segoe UI", 9)); self.status.pack(side="left", padx=8)

        self.chat = scrolledtext.ScrolledText(self.root, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.pack(fill="both", expand=True, padx=10, pady=4)

        ctrl = tk.LabelFrame(self.root, text="Steuerung", padx=8, pady=6); ctrl.pack(fill="x", padx=10, pady=4)
        r1 = tk.Frame(ctrl); r1.pack(fill="x")
        tk.Label(r1, text="Bock:").pack(side="left")
        tk.Scale(r1, from_=0, to=100, orient="horizontal", variable=self.bock_level, length=120).pack(side="left")
        tk.Label(r1, text="Stille:").pack(side="left")
        tk.Scale(r1, from_=5, to=120, orient="horizontal", variable=self.stille_toleranz, length=120).pack(side="left")
        tk.Checkbutton(r1, text="Autonom", variable=self.autonom).pack(side="left")
        tk.Checkbutton(r1, text="🔊", variable=self.vorlesen, command=lambda: setattr(self.sprecher, 'enabled', self.vorlesen.get())).pack(side="left")

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
        tk.Button(bot, text="Senden", command=self.user_send).pack(side="right")

    # --- Basis ---
    def log(self, wer, text):
        z = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal"); self.chat.insert("end", f"[{z}] {wer}: {text}\n\n")
        self.chat.configure(state="disabled"); self.chat.see("end")
    def _aktiv(self): self.letzte_user = time.time(); self.redelust = max(0, self.redelust - 2)
    def bot_sagt(self, t):
        self.log("Quassel-KI", t); self.sprecher.sprich(t)
        self.letzte_bot = time.time(); self.redelust = max(0, self.redelust - 25)
    def user_send(self):
        m = self.entry.get().strip()
        if not m: return
        self.entry.delete(0, "end"); self._aktiv(); self.log("Du", m)
        # PC-Kommandos in natürlicher Sprache
        ml = m.lower()
        if any(w in ml for w in ["projekt finden", "finde projekt", "uproject suchen"]):
            self.projekte_finden(); return
        if "actor erstellen" in ml or "neue klasse" in ml:
            self.actor_dialog(); return
        if "check" in ml and "system" in ml:
            self.neuer_check(); return
        w = finde_wissen(m)
        if w: self.root.after(500, lambda: self.bot_sagt(w)); return
        if random.randint(0, 100) < self.bock_level.get():
            self.root.after(900, lambda: self.bot_sagt("Verstanden. Wenn's um Unreal geht: frag konkret (Actor? Tick? Replication?). Oder sag 'Projekte finden'."))
        else: self.root.after(2000, lambda: self.bot_sagt("Hab grad keinen Bock. Frag später – oder besser was zu Unreal."))

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
        if self.autonom.get():
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
