"""
data_store.py modulaire : charge le profil unique (profile.json) au lieu
d'un data.json spécifique à un site. Ce profil est le CV structuré,
réutilisable sur n'importe quel formulaire.
"""
import json
from pathlib import Path

PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "profil.json"

def load_profile() -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"profile.json introuvable à {PROFILE_PATH}. "
            "Crée ce fichier avec ton CV structuré avant de lancer main.py."
        )
    with open(PROFILE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_profile(profile: dict) -> None:
    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)