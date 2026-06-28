import json
from pathlib import Path

_cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))

DEBUG_URL    = _cfg["debug_url"]
AUTO_SUBMIT  = _cfg["auto_submit"]
USE_OLLAMA   = _cfg["use_ollama"]
OLLAMA_MODEL = _cfg["ollama_model"]
VERBOSE      = _cfg["verbose"]

def log(msg: str):
    if VERBOSE:
        print(msg)