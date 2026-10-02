# -*- coding: utf-8 -*-
"""v20 Phase-2 Tests: Hardware-Klassen, Kapazitätsschutz, yaml-Konfig. Headless."""
import os
import sys
import tempfile
import unittest

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SYS not in sys.path:
    sys.path.insert(0, SYS)

from quassel import hardware as HW, konfig as KONF, modelle as R, memory2 as M2, schmiede as S, buildtest as B, impact as I


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


class MemoryPhase3Test(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pfad = os.path.join(self.tmp, "m2.json")

    def test_felder_vollstaendig(self):
        M2.hinzufuegen(self.pfad, "decision", "UBT statt Batch", quelle="chat",
                       vertrauen=0.9, projekt="SAOMMO", wichtigkeit=5,
                       ablauf="2099-01-01T00:00:00")
        e = M2.laden(self.pfad)["eintraege"][0]
        self.assertEqual(e["projekt"], "SAOMMO")
        self.assertEqual(e["wichtigkeit"], 5)
        self.assertEqual(e["ablauf"][:4], "2099")
        self.assertIn("created", e)

    def test_ablauf_wird_ignoriert_und_bereinigt(self):
        M2.hinzufuegen(self.pfad, "fact", "Alter Pfad stimmt", quelle="t",
                       ablauf="2000-01-01T00:00:00")
        M2.hinzufuegen(self.pfad, "fact", "Alter Pfad stimmt nicht", quelle="t")
        treffer = M2.abrufen(self.pfad, "Alter Pfad stimmt es?")
        self.assertFalse(any("stimmt\"" in t["content"] or t["content"] == "Alter Pfad stimmt" for t in treffer))
        n = M2.bereinigen(self.pfad)
        self.assertEqual(n, 1)
        self.assertEqual(len(M2.laden(self.pfad)["eintraege"]), 1)

    def test_projekt_boost(self):
        M2.hinzufuegen(self.pfad, "project_fact", "Engine ist Fünfachter", quelle="t", projekt="Anderes")
        M2.hinzufuegen(self.pfad, "project_fact", "Engine ist Fünfneuner", quelle="t", projekt="SAOMMO")
        treffer = M2.abrufen(self.pfad, "Welche Engine nutzen wir?", projekt="SAOMMO")
        self.assertTrue(treffer)
        self.assertEqual(treffer[0]["projekt"], "SAOMMO")

    def test_wichtigkeit_sortiert(self):
        M2.hinzufuegen(self.pfad, "fact", "Kaffee ist braun Getränk", quelle="t", wichtigkeit=1)
        M2.hinzufuegen(self.pfad, "decision", "Kaffee ist braun Beschluss", quelle="t", wichtigkeit=5)
        treffer = M2.abrufen(self.pfad, "Kaffee ist braun?")
        self.assertTrue(treffer)
        self.assertEqual(treffer[0]["type"], "decision")

    def test_episoden_einfrieren(self):
        epi = os.path.join(self.tmp, "epi.json")
        with open(epi, "w", encoding="utf-8") as f:
            import json as _j
            _j.dump([{"frage": "Wie geht Build?", "antwort": "Mit UBT und Geduld."}], f)
        n = M2.episoden_einfrieren(epi, self.pfad)
        self.assertEqual(n, 1)
        e = M2.laden(self.pfad)["eintraege"][0]
        self.assertLess(e["confidence"], 0.7)

    def test_chats_aufraeumen(self):
        import time as _t
        basis = os.path.join(self.tmp, "chats")
        os.makedirs(basis)
        alt = os.path.join(basis, "alt.json")
        neu = os.path.join(basis, "neu.json")
        open(alt, "w").write("{}")
        open(neu, "w").write("{}")
        altzeit = _t.time() - 40 * 86400
        os.utime(alt, (altzeit, altzeit))
        n = M2.chats_aufraeumen(basis, tage=30)
        self.assertEqual(n, 1)
        self.assertTrue(os.path.exists(os.path.join(basis, "archiv", "alt.json")))
        self.assertTrue(os.path.exists(neu))


class SchmiedePhase5Test(unittest.TestCase):
    def test_task_vollstaendig(self):
        t = S.task_bauen(1, "HealthComponent in C++ schreiben",
                         akzeptanz=["Heilt 25 HP"], dateien=["HealthComponent.h"],
                         testschritte=["PIE starten, Pickup einsammeln"])
        self.assertEqual(t["id"], "T001")
        self.assertEqual(t["kategorie"], "cpp")
        self.assertEqual(t["status"], "offen")
        self.assertEqual(t["akzeptanz"], ["Heilt 25 HP"])
        self.assertEqual(S.validieren([t]), [])

    def test_kategorien(self):
        self.assertEqual(S.kategorie("HUD Widget in UMG bauen"), "blueprint")
        self.assertEqual(S.kategorie("Lobby mit Server und RPC"), "multiplayer")
        self.assertEqual(S.kategorie("FPS optimieren und profilen"), "performance")
        self.assertEqual(S.kategorie("Irgendwas mit Katze"), "sonst")

    def test_validierung_findet_fehler(self):
        f = S.validieren([{"id": "T001", "ziel": "", "risiko": "extrem", "status": "vielleicht"}])
        self.assertGreaterEqual(len(f), 3)

    def test_zerlegen_kette(self):
        ts = S.zerlegen("Inventar anlegen und speichern und HUD anzeigen")
        self.assertGreaterEqual(len(ts), 3)
        self.assertEqual(ts[1]["abhaengig_von"], [ts[0]["id"]])
        self.assertEqual(S.validieren(ts), [])

    def test_markdown_import(self):
        md = "- [ ] Save System implementieren\n- [x] GDD schreiben\n- Kein Task hier\n"
        ts = S.aus_markdown(md)
        self.assertEqual(len(ts), 2)
        self.assertEqual(ts[0]["id"], "T001")
        self.assertEqual(ts[1]["status"], "fertig")
        self.assertEqual(S.validieren(ts), [])

    def test_schreiben_lesen_status(self):
        import json as _j
        d = tempfile.mkdtemp()
        p = os.path.join(d, "tasks.json")
        ts = [S.task_bauen(1, "Speichern in SaveGame"), S.task_bauen(2, "Lobby bauen")]
        ok, fehler = S.schreiben(p, ts, spiel="Demo")
        self.assertTrue(ok, fehler)
        obj = S.lesen(p)
        self.assertEqual(obj["spiel"], "Demo")
        self.assertIn("T001", S.status_text(obj))
        # kaputtes Schreiben wird abgelehnt
        ok2, f2 = S.schreiben(p, [{"id": "T001", "ziel": "", "risiko": "x", "status": "y"}])
        self.assertFalse(ok2)
        self.assertTrue(f2)


class BuildTestPhase6Test(unittest.TestCase):
    def test_unbekannte_art(self):
        ok, grund = B.befehl_bauen("rakete", "x")
        self.assertFalse(ok)

    def test_blockliste(self):
        ok, grund = B.befehl_bauen("python_skript", "x.py; rm -rf /")
        self.assertFalse(ok)

    def test_kein_shell_string(self):
        ok, befehl = B.befehl_bauen("python_test", ".")
        self.assertTrue(ok)
        self.assertIsInstance(befehl, list)  # shell=False, kein String

    def test_ue_ohne_installation_ehrlich(self):
        ok, grund = B.befehl_bauen("ue_build", "spiel.uproject", engine_pfad="C:/gibts_nicht_xyz")
        # Egal ob gefunden oder nicht: Antwort ist ehrlich formuliert
        if not ok:
            self.assertIn("nicht", grund.lower())

    def test_analyse_include(self):
        a = B.analysieren("fatal error C1083: Cannot open include file: 'Held.h'")
        self.assertTrue(a["fehler"])
        self.assertIn("Header", a["ursache"])
        self.assertTrue(a["schritte"])

    def test_analyse_leer(self):
        a = B.analysieren("Alles ok, 3 passed")
        self.assertEqual(a["fehler"], [])
        self.assertTrue(a["schritte"])

    def test_echter_lauf_python(self):
        import tempfile as _t
        d = _t.mkdtemp()
        skript = os.path.join(d, "ok_test.py")
        with open(skript, "w", encoding="utf-8") as f:
            f.write("print('läuft')\n")
        erg = B.lauf("python_skript", skript, cwd=d, timeout=60, log_ordner=os.path.join(d, "logs"))
        self.assertTrue(erg["ok"], erg)
        self.assertTrue(os.path.exists(erg["log"]))
        self.assertIn("Nächste Schritte", B.bericht(erg))

    def test_echter_lauf_fehler(self):
        import tempfile as _t
        d = _t.mkdtemp()
        skript = os.path.join(d, "kaputt_test.py")
        with open(skript, "w", encoding="utf-8") as f:
            f.write("import nicht_da_xyz\n")
        erg = B.lauf("python_skript", skript, cwd=d, timeout=60, log_ordner=os.path.join(d, "logs"))
        self.assertFalse(erg["ok"])
        self.assertTrue(erg["analyse"]["fehler"])
        self.assertIn("Paket", erg["analyse"]["ursache"])


class ImpactPhase7Test(unittest.TestCase):
    def setUp(self):
        import tempfile as _t
        self.tmp = _t.mkdtemp()
        src = os.path.join(self.tmp, "Source", "Spiel")
        os.makedirs(src)
        with open(os.path.join(src, "HeldBase.h"), "w", encoding="utf-8") as f:
            f.write("class AHeldBase {};\n")
        with open(os.path.join(src, "Gegner.cpp"), "w", encoding="utf-8") as f:
            f.write('#include "HeldBase.h"\nAHeldBase* h;\n')
        with open(os.path.join(src, "HeldBaseTest.cpp"), "w", encoding="utf-8") as f:
            f.write("TEST(AHeldBase) {}\n")
        with open(os.path.join(self.tmp, "Karte.umap"), "wb") as f:
            f.write(b"\x00AHeldBase\x00")
        with open(os.path.join(self.tmp, "Allein.cpp"), "w", encoding="utf-8") as f:
            f.write("int einsam = 1;\n")

    def test_referenzen_modul_tests(self):
        a = I.analysieren(self.tmp, "AHeldBase")
        self.assertIn(os.path.join("Source", "Spiel", "Gegner.cpp"), a["referenzen"])
        self.assertIn("Spiel", a["module"])
        self.assertEqual(len(a["tests"]), 1)

    def test_binaer_asset_gefunden(self):
        a = I.analysieren(self.tmp, "AHeldBase")
        self.assertIn("Karte.umap", a["maps_assets"])

    def test_eigene_datei_keine_referenz(self):
        a = I.analysieren(self.tmp, "AHeldBase")
        self.assertFalse(any("HeldBase.h" in r for r in a["referenzen"]))

    def test_risiko_steigt_mit_nutzern(self):
        a = I.analysieren(self.tmp, "AHeldBase")
        self.assertIn(a["risiko"], ("MEDIUM", "HIGH"))
        a2 = I.analysieren(self.tmp, "Allein")
        self.assertEqual(a2["risiko"], "LOW")

    def test_datei_risiko_config(self):
        self.assertEqual(I.datei_risiko("Config/Default.ini"), "HIGH")
        self.assertEqual(I.datei_risiko("Spiel.uproject"), "CRITICAL")
        self.assertEqual(I.datei_risiko("Source/X.cpp"), "")

    def test_bericht(self):
        b = I.bericht(I.analysieren(self.tmp, "AHeldBase"))
        self.assertIn("Empfehlung", b)


if __name__ == "__main__":
    unittest.main(verbosity=1)
