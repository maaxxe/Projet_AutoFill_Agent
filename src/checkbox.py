"""
checkbox.py modulaire : logique générique pour les cases à cocher
(conditions d'utilisation, consentement RGPD, newsletter...) qui ne
dépend d'aucune donnée du profil - juste des règles configurables.

FIX : le fichier de règles se trouve dans data/checkbox_rules.json (pas
à la racine), et ses clés sont "false_hints" / "true_hints" (pas
"decline_keywords" / "accept_keywords"). Les deux étaient incohérents
avec le code, ce qui neutralisait silencieusement toutes les règles.
"""
import json
from pathlib import Path
from .utils import normalize
from .config import log

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "checkbox_rules.json"


def load_rules() -> dict:
    if not RULES_PATH.exists():
        log(f"[CHECKBOX][WARN] fichier de règles introuvable : {RULES_PATH}")
        return {"false_hints": [], "true_hints": []}
    with open(RULES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


RULES = load_rules()


def decide_checkbox(candidates: list) -> str:
    """
    Retourne "1" (cocher) ou "0" (ne pas cocher) en fonction des règles
    de mots-clés définies dans checkbox_rules.json.

    - false_hints : la case NE DOIT PAS être cochée (ex: "j'accepte de
      recevoir des offres commerciales", "newsletter"...).
    - true_hints : la case DOIT être cochée (ex: "j'ai lu et j'accepte
      les CGU", "je ne souhaite pas recevoir de marketing"...).

    Par défaut (aucune règle qui matche) : ne pas cocher, par prudence.
    """
    text = normalize(" ".join(candidates))

    for kw in RULES.get("false_hints", []):
        if normalize(kw) in text:
            log(f"[CHECKBOX] false_hint matched: {kw!r}")
            return "0"

    for kw in RULES.get("true_hints", []):
        if normalize(kw) in text:
            log(f"[CHECKBOX] true_hint matched: {kw!r}")
            return "1"

    return "0"