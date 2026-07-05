"""
checkbox.py modulaire : logique générique pour les cases à cocher
(conditions d'utilisation, consentement RGPD, newsletter...) qui ne
dépend d'aucune donnée du profil - juste des règles configurables.
"""
import json
from pathlib import Path
from .utils import normalize
from .config import log

RULES_PATH = Path(__file__).resolve().parent.parent / "checkbox_rules.json"


def load_rules() -> dict:
    if not RULES_PATH.exists():
        return {"accept_keywords": [], "decline_keywords": []}
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


RULES = load_rules()


def decide_checkbox(candidates: list) -> str:
    """
    Retourne "1" (cocher) ou "0" (ne pas cocher) en fonction de règles
    de mots-clés définies dans checkbox_rules.json, indépendantes de tout
    site précis. Par défaut (aucune règle qui matche) : ne pas cocher,
    par prudence (RGPD, marketing, etc.).
    """
    text = normalize(" ".join(candidates))

    for kw in RULES.get("decline_keywords", []):
        if normalize(kw) in text:
            log(f"[CHECKBOX] decline_keyword matched: {kw!r}")
            return "0"

    for kw in RULES.get("accept_keywords", []):
        if normalize(kw) in text:
            log(f"[CHECKBOX] accept_keyword matched: {kw!r}")
            return "1"

    return "0"