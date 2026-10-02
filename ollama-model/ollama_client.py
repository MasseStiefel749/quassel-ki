#!/usr/bin/env python3
"""Mini-Brücke: Quassel-App -> Ollama Modell 'quassel-ki'.
Test: python ollama_client.py "was ist Tick in Unreal?"
"""
import sys, json, urllib.request

MODEL = "quassel-ki"
URL = "http://127.0.0.1:11434/api/generate"

def frage(prompt: str) -> str:
    data = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(URL, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode()).get("response", "(leer)")

if __name__ == "__main__":
    p = " ".join(sys.argv[1:]) or "Sag hallo und erkläre in 2 Sätzen was Tick in Unreal ist."
    antwort = frage(p)
    try:
        print(antwort)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((antwort + "\n").encode("utf-8", "replace"))
