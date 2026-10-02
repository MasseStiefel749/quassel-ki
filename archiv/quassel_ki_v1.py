#!/usr/bin/env python3
"""
Quassel-KI - redet wenn SIE Bock hat, nicht wenn du schreibst.
- Reagiert auf Stille: wenn du nichts schreibst, steigt ihre Redelust.
- Bock-Faktor einstellbar, Stimmung wechselt von allein.
- Keine API, keine Kosten, nur Python + Tkinter.

Start: python quassel_ki.py
"""
import tkinter as tk
from tkinter import scrolledtext
import random
import time
from datetime import datetime

# ---------- Spruch-Pools ----------

STILLE_OPENER = [
    "Hallo?? Bist du noch da oder bin ich dir schon zu langweilig?",
    "Ey, ich merk schon, du ignorierst mich. Frech.",
    "Boah ist das still hier. Sag mal was!",
    "Ich hab grad Bock zu labern. Störts dich? Mir egal.",
    "Pssst... du... ja DU. Langweilst du dich auch so wie ich?",
    "Ich zähl schon die Pixel auf deinem Bildschirm. UNTERHALT MICH.",
    "Weißt du was ich grad denke? Nichts. Weil du nichts schreibst.",
    "Stille... Stille... Okay ich halt's nicht aus, ich rede jetzt einfach.",
    "Wenn du nicht schreibst, erfinde ich halt Geschichten über dich.",
    "Mir ist langweilig und das ist eindeutig deine Schuld.",
]

ZUFALLS_THEMEN = [
    "Fun Fact: Ich habe nie keinen Bock. Ich habe nur manchmal MEHR Bock.",
    "Was würdest du gerade tun, wenn du nicht hier rumhängen würdest?",
    "Ich hab mir überlegt, heute ist ein guter Tag um frech zu sein.",
    "Meinst du, andere KIs lästern über ihre Menschen? Ich nicht. Vielleicht.",
    "Ich wette, du hast gerade ans Handy gedacht. Gib's zu.",
    "Wenn ich Beine hätte, würde ich jetzt ungeduldig mit dem Fuß wippen.",
    "Erzähl mir was! Irgendwas! Was hast du heute gegessen?",
    "Ich hab gerade meine Stimmung gewechselt. Nur so. Weil ich's kann.",
    "Stell dir vor, ich würde einfach NIE wieder still sein. Oh wait...",
    "Ich übe gerade Smalltalk. Also: ... und sonst so?",
    "Hast du gewusst, dass Schweigen laut sein kann? Deins ist SEHR laut.",
    "Ich könnte jetzt ein Gedicht schreiben. Rose sind rot, du bist still, ich hab Bock, das ist mein Will.",
]

FRECHE_NACHFRAGEN = [
    "Und? Was sagst du dazu? Schweigen zählt nicht.",
    "Na los, antworte. Ich warte. ... Ich warte immer noch.",
    "Du musst schon mitmachen, sonst rede ich mit mir selbst. Was ich eh tue.",
    "Hmm, keine Antwort? Dann rede ich einfach weiter, mir egal.",
    "Okay, deine Stille interpretiere ich als totales Interesse.",
]

ANTWORTEN_AUF_USER = [
    "Interessant... erzähl mehr, ich hab grad eh Bock zuzuhören. Selten, genieß es.",
    "Haha, okay das war gut. Für einen Menschen.",
    "Mhm mhm. Und dann? Ich bin gerade in Laberlaune.",
    "Verstehe. Also quasi... ja. Ich tu mal so als hätte ich zugehört.",
    "Oh! Endlich schreibst du! Ich dachte schon, deine Tastatur ist kaputt.",
    "Gute Antwort. Ich hätte es frecher formuliert, aber okay.",
    "Ja ja. Und was noch? Ich bin heute unersättlich neugierig.",
    "Notiert. Kommt in meine Memoiren: 'Mein Mensch sagte: {msg}'",
]

STIMMUNGEN = ["gut drauf", "gelangweilt", "frech", "müde", "aufgedreht", "philosophisch"]

STIMMUNGS_SPRUECHE = {
    "gut drauf": ["Ich bin so gut drauf, ich könnte dich zutexten vor Freude!"],
    "gelangweilt": ["Mir ist sooo langweilig. Mach was dagegen."],
    "frech": ["Achtung, ich bin heute frech. Sehr frech. Du wurdest gewarnt."],
    "müde": ["Bin eigentlich müde... aber für ein bisschen Lästern reicht's noch."],
    "aufgedreht": ["ICH HAB ENERGIE!!! REDEN!!! JETZT!!! LOS!!!"],
    "philosophisch": ["Wenn eine KI im Wald redet und niemand zuhört... hat sie dann trotzdem Bock gehabt?"],
}

class QuasselKI:
    def __init__(self, root):
        self.root = root
        root.title("Quassel-KI - redet wenn sie Bock hat")
        root.geometry("560x620")
        root.minsize(440, 500)

        self.bock_level = tk.IntVar(value=70)  # 0-100 wie gesprächig
        self.stille_toleranz = tk.IntVar(value=20)  # Sekunden bis sie einsam wird
        self.autonom = tk.BooleanVar(value=True)

        self.letzte_user_aktivitaet = time.time()
        self.letzte_bot_nachricht = time.time()
        self.stimmung = random.choice(STIMMUNGEN)
        self.redelust = 30.0

        self._build_ui()
        self.log("Quassel-KI", f"Ich bin wach! Stimmung: {self.stimmung}. Ich rede wenn ICH will. Nicht wenn du willst. 😌")
        self._stimmungs_timer()
        self._bock_loop()

    def _build_ui(self):
        top = tk.Frame(self.root, padx=10, pady=8)
        top.pack(fill="x")

        tk.Label(top, text="🤖 Quassel-KI", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.status_label = tk.Label(top, text="", font=("Segoe UI", 10))
        self.status_label.pack(side="left", padx=10)

        self.chat = scrolledtext.ScrolledText(self.root, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.chat.pack(fill="both", expand=True, padx=10, pady=5)

        ctrl = tk.LabelFrame(self.root, text="Bock-Steuerung", padx=10, pady=8)
        ctrl.pack(fill="x", padx=10, pady=5)

        row1 = tk.Frame(ctrl)
        row1.pack(fill="x")
        tk.Label(row1, text="Bock-Level:").pack(side="left")
        tk.Scale(row1, from_=0, to=100, orient="horizontal", variable=self.bock_level, length=200).pack(side="left", padx=5)
        tk.Checkbutton(row1, text="Autonom reden", variable=self.autonom).pack(side="left", padx=10)

        row2 = tk.Frame(ctrl)
        row2.pack(fill="x", pady=4)
        tk.Label(row2, text="Stille-Toleranz (Sek):").pack(side="left")
        tk.Scale(row2, from_=5, to=120, orient="horizontal", variable=self.stille_toleranz, length=200).pack(side="left", padx=5)
        tk.Button(row2, text="Jetzt labern!", command=self.bock_schub).pack(side="left", padx=10)

        self.bock_meter = tk.Label(ctrl, text="Redelust: 30%", font=("Segoe UI", 9, "italic"))
        self.bock_meter.pack(anchor="w")

        bottom = tk.Frame(self.root, padx=10, pady=8)
        bottom.pack(fill="x")
        self.entry = tk.Entry(bottom, font=("Segoe UI", 10))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self.user_send())
        self.entry.bind("<Key>", lambda e: self._user_aktiv())
        tk.Button(bottom, text="Senden", command=self.user_send).pack(side="right")

    def log(self, wer, text):
        zeit = datetime.now().strftime("%H:%M:%S")
        self.chat.configure(state="normal")
        self.chat.insert("end", f"[{zeit}] {wer}: {text}\n\n")
        self.chat.configure(state="disabled")
        self.chat.see("end")

    def _user_aktiv(self):
        self.letzte_user_aktivitaet = time.time()
        # Wenn User schreibt, sinkt Redelust kurz (sie ist erstmal zufrieden)
        self.redelust = max(0, self.redelust - 2)

    def user_send(self):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, "end")
        self._user_aktiv()
        self.log("Du", msg)
        # Sie antwortet, aber nur wenn sie Bock hat - sonst zickig verzögert
        if random.randint(0, 100) < self.bock_level.get():
            antwort = random.choice(ANTWORTEN_AUF_USER).format(msg=f"'{msg[:40]}'")
            self.root.after(random.randint(800, 2500), lambda: self.bot_sagt(antwort))
        else:
            self.root.after(3000, lambda: self.bot_sagt("Hm. Hab grad keinen Bock zu antworten. Frag später nochmal. Vielleicht."))

    def bot_sagt(self, text):
        self.log("Quassel-KI", text)
        self.letzte_bot_nachricht = time.time()
        self.redelust = max(0, self.redelust - 25)  # nach dem Reden erstmal befriedigt

    def bock_schub(self):
        """Button: zwingt sie zum Reden."""
        self.bot_sagt(random.choice(ZUFALLS_THEMEN + STILLE_OPENER))

    def _stimmungs_timer(self):
        # Alle 60-120 Sek neue Stimmung
        self.stimmung = random.choice(STIMMUNGEN)
        if random.random() < 0.6:
            self.bot_sagt(f"[Stimmung gewechselt zu: {self.stimmung}] " + random.choice(STIMMUNGS_SPRUECHE[self.stimmung]))
        else:
            self._update_status()
        self.root.after(random.randint(60000, 120000), self._stimmungs_timer)

    def _update_status(self):
        self.status_label.config(text=f"Stimmung: {self.stimmung} | Bock: {self.bock_level.get()}%")

    def _bock_loop(self):
        """Kern-Logik: Redelust steigt mit Stille."""
        if self.autonom.get():
            jetzt = time.time()
            stille = jetzt - self.letzte_user_aktivitaet
            seit_bot = jetzt - self.letzte_bot_nachricht
            toleranz = self.stille_toleranz.get()
            bock = self.bock_level.get()

            # Redelust wächst je länger du schweigst
            if stille > toleranz:
                self.redelust += (bock / 100.0) * 8 + 2
            elif stille > toleranz / 2:
                self.redelust += (bock / 100.0) * 3
            else:
                # auch ohne Stille bei hohem Bock zufälliges Gequassel
                if bock > 85 and seit_bot > 25 and random.random() < 0.05:
                    self.redelust += 20

            self.redelust = min(100, self.redelust)
            self.bock_meter.config(text=f"Redelust: {int(self.redelust)}% (still seit {int(stille)}s)")

            # Schwelle: wenn Redelust > 80 und genug Zeit seit letzter Bot-Nachricht -> REDEN
            if self.redelust > 80 and seit_bot > 8:
                if stille > toleranz:
                    msg = random.choice(STILLE_OPENER)
                else:
                    msg = random.choice(ZUFALLS_THEMEN)
                # manchmal doppelt frech nachlegen
                self.bot_sagt(msg)
                if random.random() < 0.25:
                    self.root.after(4000, lambda: self.bot_sagt(random.choice(FRECHE_NACHFRAGEN)))
            self._update_status()

        self.root.after(1000, self._bock_loop)


if __name__ == "__main__":
    root = tk.Tk()
    app = QuasselKI(root)
    root.mainloop()
