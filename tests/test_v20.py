# -*- coding: utf-8 -*-
"""v20 Phase-2 Tests: Hardware-Klassen, Kapazitätsschutz, yaml-Konfig. Headless."""
import os
import sys
import tempfile
import unittest

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SYS not in sys.path:
    sys.path.insert(0, SYS)

from quassel import hardware as HW, konfig as KONF, modelle as R


def profil_mit(vram, ram=32, gpu_namen=("Test GPU",)):
    return {"gpu": [{"name": n, "vram_mb": int(vram * 1024), "treiber": ""} for n in gpu_namen],
            "vram_gb": vram, "ram_total_gb": ram, "cpu": "Test CPU", "cpu_kerne": 8}


class KlassenTest(unittest.TestCase):
    def test_4070_high(self):
        self.assertEqual(HW.hardware_klasse(profil_mit(12, 32, ("NVIDIA GeForce RTX 4070",))), "high")

    def test_3060_12gb_medium(self):
        # 12 GB VRAM, aber 3060 -> praktisch 7-14B (E8)
        self.assertEqual(HW.hardware_klasse(profil_mit(12, 32, ("NVIDIA GeForce RTX 3060",))), "medium")

    def test_3060_8gb_medium(self):
        self.assertEqual(HW.hardware_klasse(profil_mit(8, 16, ("NVIDIA GeForce RTX 3060",))), "medium")

    def test_klein_gpu_small(self):
        self.assertEqual(HW.hardware_klasse(profil_mit(6, 64, ("NVIDIA RTX A1000 6GB Laptop GPU",))), "small")

    def test_kein_vram_cpu(self):
        self.assertEqual(HW.hardware_klasse(profil_mit(0, 16, ())), "cpu")

    def test_nur_abwaerts(self):
        # Unbekannte 16-GB-Karte bleibt high (kein Aufwärts-Schummeln nötig, kein Abwärts ohne Grund)
        self.assertEqual(HW.hardware_klasse(profil_mit(16, 64, ("NVIDIA RTX 5000",))), "high")

    def test_empfehlung_vollstaendig(self):
        e = HW.empfehlung(profil_mit(12, 32))
        for k in ("klasse", "max_modell_gb", "ctx", "ctx_max", "chat_tokens", "keep_alive", "beschreibung"):
            self.assertIn(k, e, k)
        self.assertEqual(e["klasse"], "high")
        self.assertLessEqual(e["ctx_max"], 32768)


class KapazitaetTest(unittest.TestCase):
    INST = ["quassel-ki:latest", "llama3.1:latest", "moondream:latest"]
    GROESSEN = {"quassel-ki:latest": 19.9, "llama3.1:latest": 4.9, "moondream:latest": 1.7}

    def test_grosses_modell_gesperrt(self):
        m = R.waehle_modell("coding", self.INST, None, 10.0, self.GROESSEN)
        self.assertNotEqual(m, "quassel-ki:latest")
        self.assertIsNotNone(m)  # Fallback greift, nie None bei passenden Modellen

    def test_kleines_modell_erlaubt(self):
        m = R.waehle_modell("fast", self.INST, None, 5.5, self.GROESSEN)
        self.assertEqual(m, "llama3.1:latest")

    def test_unbekannte_groesse_blockiert_nicht(self):
        m = R.waehle_modell("coding", ["mystery:neu"], None, 5.0, {})
        self.assertEqual(m, "mystery:neu")

    def test_nichts_passt_gibt_none(self):
        m = R.waehle_modell("coding", ["riese:80gb"], None, 5.0, {"riese:80gb": 80.0})
        self.assertIsNone(m)


class YamlTest(unittest.TestCase):
    def test_neue_schluessel(self):
        c = KONF.laden(os.path.join(tempfile.mkdtemp(), "x.yaml"))
        self.assertIn("max_modell_gb", c["modelle"])
        self.assertIn("budgets", c["context"])
        self.assertIn("tokens", c["chat"])
        self.assertIn("keep_alive", c["ollama"])

    def test_echte_datei(self):
        c = KONF.laden(os.path.join(SYS, "quassel.yaml"))
        self.assertEqual(c["speed"]["modus"], "SMART")
        self.assertEqual(c["context"]["budgets"]["MEDIUM"], 8192)

    def test_budget_override(self):
        b = R.context_budget("MEDIUM", 64, 10, "SMART", {"MEDIUM": 4096})
        self.assertEqual(b, 4096)


if __name__ == "__main__":
    unittest.main(verbosity=1)
