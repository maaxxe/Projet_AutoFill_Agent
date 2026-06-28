import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

config_path = ROOT_DIR / "data" / "config.json"

_cfg = json.loads(config_path.read_text(encoding="utf-8"))
DEBUG_URL    = _cfg["debug_url"]
AUTO_SUBMIT  = _cfg["auto_submit"]
USE_OLLAMA   = _cfg["use_ollama"]
OLLAMA_MODEL = _cfg["ollama_model"]
VERBOSE      = _cfg["verbose"]

def log(msg: str):
    if VERBOSE:
        print(msg)