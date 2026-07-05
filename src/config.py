import datetime
from pathlib import Path

DEBUG_URL = "http://localhost:9222"
AUTO_SUBMIT = False

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1"

LOG_FILE = Path(__file__).resolve().parent.parent / "run.log"


def log(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass