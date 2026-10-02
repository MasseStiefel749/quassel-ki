# -*- coding: utf-8 -*-
"""v19 Tests: Projekt-Scanner + Task-Discovery. Headless. Aufruf: python tests/test_v19.py"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SYS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SYS not in sys.path:
    sys.path.insert(0, SYS)

from quassel import projekte as P


def baum_anlegen():
    root = Path(tempfile.mkdtemp())
    # Unreal-Projekt
    ue = root / "MeinSpiel"
    (ue / "Source").mkdir(parents=True)
    (ue / "Content").mkdir()
    (ue / "Config").mkdir()
    (ue / "MeinSpiel.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    (ue / "ROADMAP.md").write_text(
        "# Roadmap\n- TODO: Save System implementieren\n- Multiplayer-Lobby bauen\n"
        "- Vielleicht irgendwann mal VR? (nur Idee)\n", encoding="utf-8")
    (ue / "AGENTS.md").write_text("Use C++ where possible.\n", encoding="utf-8")
    (ue / "Source" / "Held.cpp").write_text(
        "// TODO: Sprunghöhe anpassen\n// FIXME: Crash bei Null-Pointer\nint x = 1;\n", encoding="utf-8")
    (ue / "Source" / "MeinSpiel").mkdir()
    (ue / "Source" / "MeinSpiel" / "MeinSpiel.Build.cs").write_text("// build\n", encoding="utf-8")
    (ue / "Source" / "MeinSpiel" / "HeldBase.h").write_text(
        "#pragma once\n#include \"CoreMinimal.h\"\n#include \"HeldBase.generated.h\"\n"
        "UCLASS()\nclass MEINSPIEL_API AHeldBase : public ACharacter\n{\n\tGENERATED_BODY()\n};\n"
        "USTRUCT(BlueprintType)\nstruct FInventarSlot\n{\n\tGENERATED_BODY()\n};\n", encoding="utf-8")
    (ue / "Plugins" / "VRPlugin").mkdir(parents=True)
    (ue / "Plugins" / "VRPlugin" / "VRPlugin.uplugin").write_text('{"Version": 1}', encoding="utf-8")
    (ue / "Config" / "DefaultEngine.ini").write_text("[/Script/EngineSettings]\n", encoding="utf-8")
    (ue / "Content" / "Maps").mkdir(parents=True)
    (ue / "Content" / "Maps" / "Start.umap").write_bytes(b"\x00\x01fakemap")
    (ue / "Content" / "BP_Held.uasset").write_bytes(b"\x00\x01fakeasset")
    (ue / ".git").mkdir()
    # Python-Projekt
    py = root / "tool"
    py.mkdir()
    (py / "requirements.txt").write_text("x\n", encoding="utf-8")
    (py / "a.py").write_text("# TODO: Fehlerbehandlung fehlt\n", encoding="utf-8")
    (py / "b.py").write_text("print(1)\n", encoding="utf-8")
    (py / "c.py").write_text("print(2)\n", encoding="utf-8")
    (py / "README.md").write_text("# Tool\n", encoding="utf-8")
    # Kein Projekt
    (root / "leer").mkdir()
    (root / "leer" / "notizen.txt").write_text("Einkaufsliste\n", encoding="utf-8")
    return root


class ScannerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = baum_anlegen()

    def test_unreal_erkannt(self):
        idx = P.projekt_analysieren(str(self.root / "MeinSpiel"))
        self.assertEqual(idx["typ"], "unreal")
        self.assertEqual(idx["engine_version"], "5.8")
        self.assertTrue(idx["git"])
        self.assertIn("AGENTS.md", idx["regeln"])
        self.assertIn("ROADMAP.md", idx["dokus"])

    def test_python_erkannt(self):
        idx = P.projekt_analysieren(str(self.root / "tool"))
        self.assertEqual(idx["typ"], "python")

    def test_kein_projekt(self):
        typ, _ = P._ist_projekt(str(self.root / "leer"))
        self.assertIsNone(typ)

    def test_todo_gefunden(self):
        idx = P.projekt_analysieren(str(self.root / "MeinSpiel"))
        texte = [t["text"] for t in idx["tasks"]]
        self.assertTrue(any("Save System" in t for t in texte), texte)
        self.assertTrue(any("Sprung" in t for t in texte), texte)
        self.assertTrue(any("Crash" in t for t in texte), texte)

    def test_idee_niedrige_confidence(self):
        idx = P.projekt_analysieren(str(self.root / "MeinSpiel"))
        vr = [t for t in idx["tasks"] if "VR" in t["text"]]
        self.assertTrue(vr, "VR-Idee sollte gefunden sein")
        self.assertLess(vr[0]["confidence"], 0.6, vr[0])

    def test_klare_todo_hohe_confidence(self):
        idx = P.projekt_analysieren(str(self.root / "MeinSpiel"))
        save = [t for t in idx["tasks"] if "Save System" in t["text"]]
        self.assertTrue(save)
        self.assertGreaterEqual(save[0]["confidence"], 0.8)

    def test_scan_verzeichnisse(self):
        erg = P.scan_verzeichnisse([str(self.root)], tiefe=1)
        namen = {p["name"] for p in erg}
        self.assertIn("MeinSpiel", namen)
        self.assertIn("tool", namen)
        self.assertNotIn("leer", namen)

    def test_top_tasks_filter(self):
        erg = P.scan_verzeichnisse([str(self.root)], tiefe=1)
        top = P.top_tasks(erg, min_confidence=0.8, max_risk="MEDIUM")
        self.assertTrue(top, "sollte sichere Tasks finden")
        for t in top:
            self.assertGreaterEqual(t["confidence"], 0.8)
            self.assertIn(t["risk"], ("LOW", "MEDIUM"))

    def test_bericht(self):
        erg = P.scan_verzeichnisse([str(self.root)], tiefe=1)
        b = P.tasks_bericht(erg)
        self.assertIn("MeinSpiel", b)
        self.assertIn("Regeln: AGENTS.md", b)

    def test_risiko(self):
        self.assertEqual(P._risiko_einschaetzen("Alte Dateien löschen und aufräumen"), "CRITICAL")
        self.assertEqual(P._risiko_einschaetzen("Netzwerk-Replikation umbauen"), "HIGH")
        self.assertEqual(P._risiko_einschaetzen("Doku aktualisieren"), "LOW")


class UnrealDetailsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = baum_anlegen()
        cls.idx = P.projekt_analysieren(str(cls.root / "MeinSpiel"))

    def test_schema_version(self):
        self.assertEqual(self.idx.get("schema"), 2)

    def test_modul(self):
        module = {m["name"]: m for m in self.idx["unreal"]["module"]}
        self.assertIn("MeinSpiel", module)
        self.assertTrue(module["MeinSpiel"]["build_cs"])

    def test_plugin_config_map(self):
        self.assertTrue(any("VRPlugin.uplugin" in p for p in self.idx["unreal"]["plugins"]))
        self.assertTrue(any("DefaultEngine.ini" in c for c in self.idx["unreal"]["configs"]))
        self.assertTrue(any("Start.umap" in m for m in self.idx["unreal"]["maps"]))

    def test_klassen_geparst(self):
        namen = {(k["name"], k["art"]) for k in self.idx["unreal"]["klassen"]}
        self.assertIn(("AHeldBase", "UCLASS"), namen)
        self.assertIn(("FInventarSlot", "USTRUCT"), namen)

    def test_blueprint_nur_pfad(self):
        bps = self.idx["unreal"]["blueprints"]
        self.assertTrue(any("BP_Held.uasset" in b["pfad"] for b in bps))
        self.assertTrue(all("bytes" in b for b in bps))  # kein erfundener Inhalt

    def test_kaputte_datei_bricht_nicht_ab(self):
        kaputt = self.root / "MeinSpiel" / "Kaputt.uproject"
        kaputt.write_bytes(b"\xff\xfe kein json \x00")
        try:
            idx = P.projekt_analysieren(str(self.root / "MeinSpiel"))
            self.assertEqual(idx["typ"], "unreal")  # Scan überlebt
        finally:
            kaputt.unlink()


if __name__ == "__main__":
    unittest.main(verbosity=1)
