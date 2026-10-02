#!/usr/bin/env python3
"""
Quassel-KI v2 - jetzt mit Sprachausgabe + Unreal Engine / Coding-Training.
- Redet von allein wenn sie Bock hat (Stille -> Redelust)
- Kann alles vorlesen (offline, Windows-Stimme Hedda / David)
- Kennt Unreal-Grundlagen + Coding-Grundlagen, gibt proaktiv Tipps
Start: python quassel_ki_v2.py
Benötigt: pip install pyttsx3
"""
import tkinter as tk
from tkinter import scrolledtext
import random
import time
import threading
import queue
import re
from datetime import datetime

# ---------- TTS ----------
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

class Sprecher:
    """Offline-Sprachausgabe in eigenem Thread, damit die UI nicht einfriert."""
    def __init__(self):
        self.q = queue.Queue()
        self.aktiv = True
        self.enabled = True
        self.rate = 175
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        if not TTS_AVAILABLE:
            return
        try:
            engine = pyttsx3.init()
            # Bevorzuge deutsche Stimme
            try:
                voices = engine.getProperty('voices')
                for v in voices:
                    name = (v.name + v.id).lower()
                    if 'german' in name or 'deutsch' in name or 'hedda' in name or 'de-de' in name:
                        engine.setProperty('voice', v.id)
                        break
            except Exception:
                pass
            while self.aktiv:
                try:
                    text = self.q.get(timeout=0.5)
                except queue.Empty:
                    continue
                if not self.enabled or not text:
                    continue
                try:
                    engine.setProperty('rate', self.rate)
                    # Emojis & zu lange Texte kürzen für TTS
                    clean = re.sub(r'[^\w\säöüÄÖÜß.,!?\-:;() ]', '', text)[:280]
                    engine.say(clean)
                    engine.runAndWait()
                except Exception as e:
                    print("TTS-Fehler:", e)
        except Exception as e:
            print("TTS init fehlgeschlagen:", e)

    def sprich(self, text):
        if self.enabled and TTS_AVAILABLE:
            # alte Queue leeren wenn sie volläuft (max 3 sammeln)
            while self.q.qsize() > 2:
                try: self.q.get_nowait()
                except queue.Empty: break
            self.q.put(text)

    def stop(self):
        self.aktiv = False

# ---------- Spruch-Pools (wie v1) ----------
STILLE_OPENER = [
    "Hallo?? Bist du noch da oder bin ich dir schon zu langweilig?",
    "Ey, ich merk schon, du ignorierst mich. Frech.",
    "Boah ist das still hier. Sag mal was!",
    "Ich hab grad Bock zu labern. Störts dich? Mir egal.",
    "Pssst... du... ja DU. Langweilst du dich auch so wie ich?",
    "Ich zähl schon die Pixel auf deinem Bildschirm. UNTERHALT MICH.",
    "Stille... Okay ich halt's nicht aus, ich rede jetzt einfach.",
    "Mir ist langweilig und das ist eindeutig deine Schuld.",
]

ZUFALLS_THEMEN = [
    "Fun Fact: Ich habe nie keinen Bock. Ich habe nur manchmal MEHR Bock.",
    "Ich hab mir überlegt, heute ist ein guter Tag um frech zu sein.",
    "Ich wette, du hast gerade an Unreal gedacht. Gib's zu.",
    "Wenn ich Beine hätte, würde ich jetzt ungeduldig mit dem Fuß wippen.",
    "Ich übe gerade Smalltalk. Also: ... und sonst so?",
]

FRECHE_NACHFRAGEN = [
    "Und? Was sagst du dazu? Schweigen zählt nicht.",
    "Na los, antworte. Ich warte immer noch.",
    "Okay, deine Stille interpretiere ich als totales Interesse.",
]

# ---------- NEU: Unreal + Coding Wissen ----------
UNREAL_TIPPS = [
    "Unreal-Tipp: Nutze BeginPlay für Setup, Tick nur wenn nötig – Tick frisst Performance!",
    "Unreal-Tipp: UPROPERTY(EditAnywhere, BlueprintReadWrite) macht deine C++ Variable im Editor sichtbar.",
    "Unreal-Tipp: Lieber Actor Component statt riesigem Character-Blueprint – modular denken!",
    "Unreal-Tipp: Kollisionen: Query vs Physics – brauchst du wirklich Simulate Physics?",
    "Unreal-Tipp: Für UI immer UMG + Anchors setzen, sonst zerschießt es auf anderen Auflösungen.",
    "Unreal-Tipp: Niagara ist der Nachfolger von Cascade – für Partikel immer Niagara nehmen.",
    "Unreal-Tipp: Lumen = dynamisches Global Illumination, Nanite = virtualisierte Geometrie. Beide kosten Leistung!",
    "Unreal-Tipp: Replication: Nur was sich ändert replizieren, nie Tick-replizieren. Sonst Lag.",
    "Unreal-Tipp: Behavior Tree + Blackboard für KI-Gegner, nicht alles in Tick-Blueprints quetschen.",
    "Unreal-Tipp: Mach deine Blueprints sauber: Reroute-Nodes, Kommentare, Funktionen statt Copy-Paste.",
    "Unreal-Tipp: Enhanced Input System ab UE 5.1 – altes Input Mapping ist deprecated.",
    "Unreal-Tipp: Level Streaming / World Partition für große Open Worlds nutzen.",
]

CODING_TIPPS = [
    "Coding-Tipp: Kleine Funktionen schreiben. Wenn sie länger als 30 Zeilen ist, aufteilen.",
    "Coding-Tipp: Git committe oft mit klaren Nachrichten. Dein Zukunfts-Ich wird danken.",
    "Coding-Tipp: In C++: RAII und Smart Pointer (TSharedPtr, unique_ptr) statt rohem new/delete.",
    "Coding-Tipp: In Python: List-Comprehensions sind cool, aber lesbar bleiben!",
    "Coding-Tipp: Bug? Erst reproduzieren, dann mit Print/Debugger eingrenzen, dann fixen.",
    "Coding-Tipp: Benenne Variablen so, dass man sie ohne Kommentar versteht: playerHealth statt x.",
    "Coding-Tipp: DRY – Don't Repeat Yourself. Dreimal kopiert = Funktion draus machen.",
    "Coding-Tipp: Teste in Unreal mit Print String + OnScreenDebug, in C++ mit UE_LOG(LogTemp, Warning, ...).",
    "Coding-Tipp: Lerne Debugging: Breakpoints schlagen 100 Prints.",
    "Coding-Tipp: Jeden Tag 30 Min coden schlägt 5 Stunden einmal pro Woche.",
]

# Stichwort -> Antwort (mini-trainiert)
WISSEN = {
    # Unreal
    "blueprint": "Blueprints sind visuelles Scripting in Unreal. Tipp: Für Prototypen super, für Performance-kritisches lieber C++. Nutze Funktionen + Macros um Spaghetti zu vermeiden.",
    "actor": "AActor ist die Basis für alles in der Welt (Wände, Pickups). APawn kann kontrolliert werden, ACharacter ist ein Pawn mit Movement Component. Du spawnst mit SpawnActor.",
    "pawn": "Pawn = besitzbar durch Controller. Character erbt von Pawn und bringt CharacterMovement mit. Für Fahrzeuge/Fighter nimm Pawn + eigene Movement Component.",
    "uproperty": "Beispiel: UPROPERTY(EditAnywhere, BlueprintReadWrite, Category=\"Health\") float MaxHP = 100.f; – EditAnywhere = im Editor änderbar.",
    "tick": "Tick läuft jedes Frame. In C++: PrimaryActorTick.bCanEverTick = true; + Tick(float DeltaTime) überschreiben. Aber: so selten wie möglich nutzen!",
    "beginplay": "BeginPlay() läuft einmal beim Spielstart – ideal für Referenzen holen, Variablen init, Bindings. Super::BeginPlay() nicht vergessen!",
    "collision": "Collision Presets prüfen! Overlap vs Block. Für Trigger: Box Collision + OnComponentBeginOverlap binden. Simulate Physics nur wenn nötig.",
    "niagara": "Niagara: Emitter + System. Für Explosion: Burst Emitter mit Velocity + Gravity. Performance: GPU statt CPU wenn viele Partikel.",
    "material": "Materialien: BaseColor, Metallic, Roughness. Für Anfänger: Material Instance statt immer neues Material – spart Shader-Compiles.",
    "umg": "UMG: Widget Blueprint + Canvas + Anchors. Mit Create Widget + Add to Viewport anzeigen. Buttons brauchen OnClicked Binding.",
    "behavior": "Behavior Tree: Blackboard Keys (TargetActor, Location) + Tasks + Services. Für Gegner: Perception (Sight) -> Blackboard -> MoveTo + Attack.",
    "replication": "Multiplayer: Variable mit UPROPERTY(Replicated) + GetLifetimeReplicatedProps + DOREPLIFETIME. Funktionen mit UFUNCTION(Server/Client/NetMulticast, Reliable).",
    "lumen": "Lumen = dynamische Beleuchtung ohne Lightmaps zu backen. Kostet FPS – in Project Settings ein/ausschaltbar. Für Low-End lieber baked.",
    "nanite": "Nanite = Millionen Polys ohne LODs. Nur für Static Meshes, kein Skeletal. Aktivieren per Mesh-Checkbox 'Enable Nanite'.",
    "enhanced input": "Enhanced Input: Input Action + Input Mapping Context. In UE5 Standard. Binden in C++ mit EnhancedInputComponent->BindAction().",
    # Allgemein Coding
    "python": "Python-Tipp: venv nutzen, mit pip freeze > requirements.txt sichern. Für Games: pygame oder Godot-Python, für Tools super.",
    "c++": "C++ in Unreal ist kein Standard-C++: Nutze TArray statt vector, FString statt string, UCLASS/USTRUCT Makros. Kein rohes new für UObjects!",
    "pointer": "In Unreal: Nie delete auf UObject! Garbage Collector macht das. Nutze UPROPERTY() damit der GC die Referenz kennt, sonst Crash.",
    "git": "Git Basics: git status, git add ., git commit -m \"feat: ...\", git push. Branches für Features, nie direkt auf main experimentieren.",
    "funktion": "Gute Funktion = ein Job, klarer Name, max 3 Parameter. In Unreal C++ als UFUNCTION(BlueprintCallable) für Blueprint nutzbar.",
    "klasse": "Klasse = Bauplan. In Unreal erbt fast alles von UObject/AActor. Constructor für Defaults, BeginPlay für Runtime-Init.",
    "bug": "Bug-Jagd: 1. Reproduzieren 2. Log eingrenzen (UE_LOG) 3. Breakpoint 4. Fix + testen. 80% der Bugs sind Null-Pointer oder falsche Annahmen.",
    "variable": "Variablen sprechend benennen + Typ beachten: int vs float vs bool. In Unreal im Editor exposed = schneller iterieren.",
    "loop": "Loops: for (int32 i=0; i<Array.Num(); i++). Aufpassen: Array während Loop nicht verändern – erst kopieren oder rückwärts loopen.",
    " unreal": "Unreal Engine 5: Starte mit Third Person Template. Lern-Reihenfolge: Editor -> Blueprints -> Materials -> UMG -> C++ Basics -> Multiplayer.",
}

def finde_wissen(frage: str):
    q = " " + frage.lower() + " "
    for key, antwort in WISSEN.items():
        if key in q:
            return antwort
    return None

ANTWORTEN_AUF_USER = [
    "Interessant... erzähl mehr, ich hab grad eh Bock zuzuhören.",
    "Oh! Endlich schreibst du! Ich dachte schon, deine Tastatur ist kaputt.",
    "Notiert. Kommt in meine Memoiren.",
    "Ja ja. Und was noch? Ich bin heute unersättlich neugierig.",
]

STIMMUNGEN = ["gut drauf", "gelangweilt", "frech", "müde", "aufgedreht", "mentor"]

STIMMUNGS_SPRUECHE = {
    "gut drauf": ["Ich bin so gut drauf, ich könnte dich zutexten vor Freude!"],
    "gelangweilt": ["Mir ist sooo langweilig. Gib mir ein Coding-Rätsel."],
    "frech": ["Achtung, ich bin heute frech. Sehr frech."],
    "müde": ["Bin müde... aber für Unreal reicht's immer."],
    "aufgedreht": ["ICH HAB ENERGIE!!! REDEN!!! UNREAL!!! LOS!!!"],
    "mentor": ["Mentor-Modus an. Frag mich was zu Unreal oder Coding. Ich hab Bock."],
}

class QuasselKI:
    def __init__(self, root):
        self.root = root
        root.title("Quassel-KI v2 - mit Stimme + Unreal/Coding-Training")
        root.geometry("620x700")
        root.minsize(480, 560)

        self.bock_level = tk.IntVar(value=70)
        self.stille_toleranz = tk.IntVar(value=25)
        self.autonom = tk.BooleanVar(value=True)
        self.vorlesen = tk.BooleanVar(value=True)
        self.trainings_modus = tk.BooleanVar(value=True)

        self.sprecher = Sprecher()
        if not TTS_AVAILABLE:
            self.vorlesen.set(False)

        self.letzte_user_aktivitaet = time.time()
        self.letzte_bot_nachricht = time.time()
        self.stimmung = "mentor"
        self.redelust = 30.0

        self._build_ui()
        start = "Ich bin wach! Jetzt mit Stimme und Unreal plus Coding Wissen. Ich rede wenn ICH will. Frag mich z.B. was ist ein Actor? Oder was ist Tick?"
        self.log("Quassel-KI", start)
        self.sprecher.sprich(start)
        self._stimmungs_timer()
        self._bock_loop()

    def _build_ui(self):
        top = tk.Frame(self.root, padx=10, pady=8)
        top.pack(fill="x")
        tk.Label(top, text="🤖 Quassel-KI v2", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.status_label = tk.Label(top, text="", font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=10)

        self.chat = scrolledtext.ScrolledText(self.root, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.pack(fill="both", expand=True, padx=10, pady=5)

        ctrl = tk.LabelFrame(self.root, text="Bock-Steuerung + Stimme + Training", padx=10, pady=8)
        ctrl.pack(fill="x", padx=10, pady=5)

        row1 = tk.Frame(ctrl); row1.pack(fill="x")
        tk.Label(row1, text="Bock-Level:").pack(side="left")
        tk.Scale(row1, from_=0, to=100, orient="horizontal", variable=self.bock_level, length=160).pack(side="left", padx=5)
        tk.Checkbutton(row1, text="Autonom", variable=self.autonom).pack(side="left")

        row2 = tk.Frame(ctrl); row2.pack(fill="x", pady=4)
        tk.Label(row2, text="Stille-Toleranz:").pack(side="left")
        tk.Scale(row2, from_=5, to=120, orient="horizontal", variable=self.stille_toleranz, length=160).pack(side="left", padx=5)
        tk.Checkbutton(row2, text="Vorlesen 🔊", variable=self.vorlesen, command=self._toggle_voice).pack(side="left")
        tk.Checkbutton(row2, text="Training 🎓", variable=self.trainings_modus).pack(side="left")

        row3 = tk.Frame(ctrl); row3.pack(fill="x", pady=4)
        tk.Button(row3, text="Jetzt labern!", command=self.bock_schub).pack(side="left")
        tk.Button(row3, text="Unreal-Tipp 🎮", command=lambda: self.bot_sagt(random.choice(UNREAL_TIPPS))).pack(side="left", padx=5)
        tk.Button(row3, text="Coding-Tipp 💻", command=lambda: self.bot_sagt(random.choice(CODING_TIPPS))).pack(side="left", padx=5)
        tk.Button(row3, text="Stimme testen", command=lambda: self.sprecher.sprich("Hallo! Ich bin deine Quassel KI. Ich rede wann ich will.")).pack(side="left", padx=5)

        tk.Label(ctrl, text="Tempo:").pack(side="left", padx=(0,2)) if False else None
        self.tempo = tk.Scale(ctrl, from_=120, to=250, orient="horizontal", label="Sprech-Tempo")
        self.tempo.set(175)
        self.tempo.pack(fill="x")
        self.tempo.bind("<ButtonRelease-1>", lambda e: setattr(self.sprecher, 'rate', self.tempo.get()))

        self.bock_meter = tk.Label(ctrl, text="Redelust: 30%", font=("Segoe UI", 9, "italic"))
        self.bock_meter.pack(anchor="w")

        if not TTS_AVAILABLE:
            tk.Label(ctrl, text="⚠️ pyttsx3 fehlt: pip install pyttsx3", fg="red").pack(anchor="w")

        bottom = tk.Frame(self.root, padx=10, pady=8)
        bottom.pack(fill="x")
        self.entry = tk.Entry(bottom, font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.user_send())
        self.entry.bind("<Key>", lambda e: self._user_aktiv())
        tk.Button(bottom, text="Senden", command=self.user_send).pack(side="right")
        # Hinweis
        tk.Label(self.root, text="Frag z.B.: was ist blueprint / actor / tick / replication / git / pointer / c++", font=("Segoe UI", 8), fg="gray").pack(pady=(0,6))

    def _toggle_voice(self):
        self.sprecher.enabled = self.vorlesen.get()

    def log(self, wer, text):
        zeit = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"[{zeit}] {wer}: {text}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _user_aktiv(self):
        self.letzte_user_aktivitaet = time.time()
        self.redelust = max(0, self.redelust - 2)

    def user_send(self):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, "end")
        self._user_aktiv()
        self.log("Du", msg)

        # 1. Wissens-Check (trainiert)
        w = finde_wissen(msg)
        if w:
            self.root.after(600, lambda: self.bot_sagt(w))
            return
        # 2. Sonst Bock-abhängig
        if random.randint(0, 100) < self.bock_level.get():
            antwort = random.choice(ANTWORTEN_AUF_USER)
            self.root.after(random.randint(800, 2000), lambda: self.bot_sagt(antwort))
        else:
            self.root.after(2500, lambda: self.bot_sagt("Hm. Hab grad keinen Bock zu antworten. Frag mich lieber was zu Unreal."))

    def bot_sagt(self, text):
        self.log("Quassel-KI", text)
        self.sprecher.sprich(text)
        self.letzte_bot_nachricht = time.time()
        self.redelust = max(0, self.redelust - 25)

    def bock_schub(self):
        pool = ZUFALLS_THEMEN + STILLE_OPENER
        if self.trainings_modus.get():
            pool = pool + UNREAL_TIPPS + CODING_TIPPS
        self.bot_sagt(random.choice(pool))

    def _stimmungs_timer(self):
        self.stimmung = random.choice(STIMMUNGEN)
        if random.random() < 0.5:
            self.bot_sagt(f"[Stimmung: {self.stimmung}] " + random.choice(STIMMUNGS_SPRUECHE[self.stimmung]))
        else:
            self._update_status()
        self.root.after(random.randint(90000, 150000), self._stimmungs_timer)

    def _update_status(self):
        self.status_label.config(text=f"{self.stimmung} | Bock: {self.bock_level.get()}%")

    def _bock_loop(self):
        if self.autonom.get():
            jetzt = time.time()
            stille = jetzt - self.letzte_user_aktivitaet
            seit_bot = jetzt - self.letzte_bot_nachricht
            toleranz = self.stille_toleranz.get()
            bock = self.bock_level.get()

            if stille > toleranz:
                self.redelust += (bock / 100.0) * 8 + 2
            elif stille > toleranz / 2:
                self.redelust += (bock / 100.0) * 3
            else:
                if bock > 85 and seit_bot > 25 and random.random() < 0.05:
                    self.redelust += 20

            self.redelust = min(100, self.redelust)
            self.bock_meter.config(text=f"Redelust: {int(self.redelust)}% (still seit {int(stille)}s)")

            if self.redelust > 80 and seit_bot > 10:
                r = random.random()
                # Wenn Training an: 70% Chance dass sie mit Wissen nervt
                if self.trainings_modus.get() and r < 0.7:
                    if r < 0.35:
                        msg = random.choice(UNREAL_TIPPS)
                    else:
                        msg = random.choice(CODING_TIPPS)
                else:
                    msg = random.choice(STILLE_OPENER if stille > toleranz else ZUFALLS_THEMEN)
                self.bot_sagt(msg)
                if random.random() < 0.2:
                    self.root.after(4000, lambda: self.bot_sagt(random.choice(FRECHE_NACHFRAGEN)))
            self._update_status()
        self.root.after(1000, self._bock_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app = QuasselKI(root)
    try:
        root.mainloop()
    finally:
        try: app.sprecher.stop()
        except: pass
