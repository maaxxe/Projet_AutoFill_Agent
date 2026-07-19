"""
config.py : charge la configuration depuis data/config.json (source de
vérité unique), avec des valeurs de repli si le fichier est absent ou
incomplet.

AVANT ce fix : OLLAMA_MODEL était codé en dur ("llama3.1") indépendamment
du contenu de data/config.json (qui indiquait "qwen2.5-coder:14b").
Le modèle réellement utilisé ne correspondait donc jamais à la config
voulue -> régression silencieuse.
"""
import datetime
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "config.json"

_DEFAULTS = {
    "debug_url": "http://localhost:9222",
    "auto_submit": False,
    "use_ollama": True,
    "ollama_model": "qwen2.5-coder:14b",
    "verbose": True,
    "num_ctx": 8192,
    "num_predict": 500,
}


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return dict(_DEFAULTS)
    merged = dict(_DEFAULTS)
    merged.update(data)
    return merged


_CONFIG = _load_config()

DEBUG_URL = _CONFIG["debug_url"]
AUTO_SUBMIT = bool(_CONFIG["auto_submit"])
USE_OLLAMA = bool(_CONFIG["use_ollama"])
VERBOSE = bool(_CONFIG["verbose"])

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = _CONFIG["ollama_model"]
OLLAMA_OPTIONS = {
    "temperature": 0,
    "num_ctx": _CONFIG["num_ctx"],
    "num_predict": _CONFIG["num_predict"],
}

LOG_FILE = Path(__file__).resolve().parent.parent / "run.log"


def log(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    if VERBOSE:
        print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass