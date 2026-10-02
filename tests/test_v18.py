# -*- coding: utf-8 -*-
"""v18 Modul-Tests. Headless, kein Modell nötig. Aufruf: python tests/test_v18.py"""
import json
import os
import sys
import tempfile
import unittest

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SYS not in sys.path:
    sys.path.insert(0, SYS)

from quassel import hardware, konfig, memory2, modelle


class HardwareTest(unittest.TestCase):
    def test_profil_struktur(self):
        p = hardware.profil()
        for feld in ("gpu", "vram_gb", "ram_total_gb", "cpu", "cpu_kerne",
                     "cuda", "ollama", "modelle_installiert", "kapazitaet", "modus"):
            self.assertIn(feld, p, feld)
        self.assertIsInstance(p["gpu"], list)
        self.assertGreaterEqual(p["ram_total_gb"], 1)
        self.assertGreaterEqual(p["cpu_kerne"], 1)

    def test_profil_text_ohne_crash(self):
        t = hardware.profil_text()
        self.assertIn("QUASSEL HARDWARE", t)
        self.assertIn("MODEL CAPACITY", t)


class ModelleTest(unittest.TestCase):
    INST = ["quassel-ki:latest", "llama3.1:latest", "moondream:latest"]

    def test_schwierigkeit_trivial(self):
        stufe, _ = modelle.schwierigkeit("hallo")
        self.assertEqual(stufe, "TRIVIAL")

    def test_schwierigkeit_code(self):
        stufe, _ = modelle.schwierigkeit("Mein C++ Code crasht mit nullptr in der Build.cs, hier der Traceback:\nZeile 1\nZeile 2\nZeile 3\nZeile 4\nZeile 5")
        self.assertEqual(stufe, "MEDIUM")

    def test_schwierigkeit_max(self):
        stufe, _ = modelle.schwierigkeit(
            "Analysiere die komplette Multiplayer-Server-Architektur mit Netzwerk-Replikation "
            "und entwirf ein Konzept für die Roadmap inklusive Strategie für tausende Spieler")
        self.assertIn(stufe, ("HIGH", "MAX"))

    def test_rollenauswahl(self):
        self.assertEqual(modelle.waehle_modell("fast", self.INST), "llama3.1:latest")
        self.assertEqual(modelle.waehle_modell("coding", self.INST), "quassel-ki:latest")
        self.assertEqual(modelle.waehle_modell("vision", self.INST), "moondream:latest")

    def test_fallbackkette(self):
        # Nichts Passendes -> fallback -> irgendein installiertes
        m = modelle.waehle_modell("coding", ["irgendein-modell:neu"])
        self.assertEqual(m, "irgendein-modell:neu")
        self.assertIsNone(modelle.waehle_modell("coding", []))

    def test_speed_modes(self):
        self.assertEqual(modelle.speed_rolle("HIGH", False, True, "FAST"), "fast")
        self.assertEqual(modelle.speed_rolle("MAX", False, True, "MAXIMUM"), "reasoning")
        self.assertEqual(modelle.speed_rolle("TRIVIAL", False, False, "SMART"), "fast")
        self.assertEqual(modelle.speed_rolle("LOW", True, False, "FAST"), "vision")

    def test_context_budget_deckel(self):
        self.assertEqual(modelle.context_budget("TRIVIAL"), 4096)
        self.assertEqual(modelle.context_budget("MAX", ram_gb=8), 8192)
        self.assertLessEqual(modelle.context_budget("MAX", ram_gb=64, modell_gb=30), 32768)

    def test_protokoll(self):
        p = modelle.entscheidungs_protokoll("hallo", "SMART")
        self.assertEqual(p["rolle"], "fast")
        self.assertIn("schwere", p)


class Memory2Test(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.pfad = os.path.join(d, "mem2.json")

    def test_typen_und_dedup(self):
        memory2.hinzufuegen(self.pfad, "project_fact", "SAOMMO nutzt UE 5.8", "SAOMMO-KONTEXT.md", 1.0)
        memory2.hinzufuegen(self.pfad, "project_fact", "SAOMMO nutzt UE 5.8", "chat", 0.5)
        daten = memory2.laden(self.pfad)
        self.assertEqual(len(daten["eintraege"]), 1)
        self.assertEqual(daten["eintraege"][0]["confidence"], 1.0)

    def test_ungueltiger_typ(self):
        e = memory2.neu("blödsinn", "x")
        self.assertEqual(e["type"], "unknown")

    def test_migration(self):
        alt = os.path.join(os.path.dirname(self.pfad), "alt.json")
        with open(alt, "w", encoding="utf-8") as f:
            json.dump({"fakten": ["Nutzer mag Kaffee"]}, f)
        n = memory2.migrieren(alt, self.pfad)
        self.assertEqual(n, 1)
        e = memory2.laden(self.pfad)["eintraege"][0]
        self.assertEqual(e["type"], "fact")
        self.assertLess(e["confidence"], 0.7)

    def test_retrieval(self):
        memory2.hinzufuegen(self.pfad, "decision", "Build-System ist UnrealBuildTool wegen Modulen", "chat", 0.9)
        memory2.hinzufuegen(self.pfad, "fact", "Lieblingsfarbe ist Blau", "chat", 0.9)
        treffer = memory2.abrufen(self.pfad, "Welches Build-System nutzen wir für Module?")
        self.assertTrue(any("Build" in t["content"] for t in treffer))
        self.assertFalse(any("Blau" in t["content"] for t in treffer))

    def test_veraltet(self):
        memory2.hinzufuegen(self.pfad, "fact", "Engine ist 5.8", "x", 1.0)
        memory2.veraltet_markieren(self.pfad, "Engine ist 5.8")
        e = memory2.laden(self.pfad)["eintraege"][0]
        self.assertEqual(e["type"], "hypothesis")


class KonfigTest(unittest.TestCase):
    def test_defaults_ohne_datei(self):
        c = konfig.laden(os.path.join(tempfile.mkdtemp(), "gibts_nicht.yaml"))
        self.assertEqual(c["speed"]["modus"], "SMART")
        self.assertTrue(c["agent"]["self_check"])

    def test_yaml_merge(self):
        d = tempfile.mkdtemp()
        p = os.path.join(d, "q.yaml")
        with open(p, "w", encoding="utf-8") as f:
            f.write("speed:\n  modus: FAST\n")
        c = konfig.laden(p)
        self.assertEqual(c["speed"]["modus"], "FAST")
        self.assertEqual(c["quassel"]["sprache"], "de")


if __name__ == "__main__":
    unittest.main(verbosity=1)
