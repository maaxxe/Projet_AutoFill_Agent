"""
Resolver modulaire v4 :
- Ajoute la gestion déterministe du groupe 2 (attestations/certifications
  professionnelles type "ing." sur CN360), absent du profil -> skip propre
  au lieu de laisser Ollama deviner et halluciner du texte long dans les
  champs "Date de réception" ou "Si autre, veuillez préciser".
- Garde la logique v3 pour groupe 0 (expérience) et groupe 1 (formation).
"""
import re
from src.config import log
from src.ollama_utils import ask_ollama_for_field

REPEATED_PATTERN = re.compile(r"(\d+)_(\d+)_(\d+)")

EXPERIENCE_COLUMN_MAP = {0: "poste", 1: "entreprise", 2: "date_debut", 3: "date_fin"}

FORMATION_FIELD_TYPE = [
    (["si autre", "veuillez préciser"], "institution_autre_text"),
    (["institution", "établissement"], "institution_select"),
    (["programme"], "programme_select"),
    (["majeur"], "majeure"),
    (["mineure"], "mineure"),
    (["date d'obtention", "date obtention", "diplôme"], "date_obtention"),
]

CERTIFICATION_COLUMN_MAP = {0: "titre", 1: "autre_texte", 2: "date_reception", 3: "date_expiration"}

AUTRE_KEYWORDS = ["autre", "other", "monde entier", "université du monde entier", "non listé"]


def detect_repeated_field(candidates: list):
    for raw in candidates:
        m = REPEATED_PATTERN.search(raw)
        if m:
            groupe, ligne, colonne = (int(x) for x in m.groups())
            return groupe, ligne, colonne
    return None


def classify_formation_field(candidates: list) -> str:
    text = " ".join(candidates).lower()
    for keywords, kind in FORMATION_FIELD_TYPE:
        if any(kw in text for kw in keywords):
            return kind
    return ""


def resolve_experience_field(profile: dict, ligne: int, colonne: int):
    experiences = profile.get("experiences", [])
    if ligne >= len(experiences):
        return ""
    champ = EXPERIENCE_COLUMN_MAP.get(colonne)
    if not champ:
        return ""
    return experiences[ligne].get(champ, "")


def find_autre_option(available_options: list):
    if not available_options:
        return None
    for opt in available_options:
        opt_low = opt.lower()
        if any(kw in opt_low for kw in AUTRE_KEYWORDS):
            return opt
    return None


def resolve_formation_field(profile: dict, ligne: int, candidates: list,
                             tag: str, available_options: list = None):
    formations = profile.get("formations", [])
    log(f"[DEBUG_FORMATION] ligne={ligne} | total_formations={len(formations)} | "
        f"contenu={formations[ligne] if ligne < len(formations) else 'HORS INDEX'}")

    if ligne >= len(formations):
        return ""
    formation = formations[ligne]
    kind = classify_formation_field(candidates)
    log(f"[DEBUG_FORMATION] kind_detecte={kind} pour candidates={candidates}")


    if kind == "institution_select":
        if tag == "select":
            autre = find_autre_option(available_options)
            return autre or ""
        return formation.get("institution", "")

    if kind == "institution_autre_text":
        return formation.get("institution", "")

    if kind == "programme_select":
        if tag == "select":
            programme = formation.get("programme", "")
            if available_options:
                low_opts = [o.lower() for o in available_options]
                if not any(programme.lower() in o or o in programme.lower() for o in low_opts):
                    autre = find_autre_option(available_options)
                    if autre:
                        return autre
            return programme
        return formation.get("programme", "")

    if kind == "majeure":
        return formation.get("majeure", "")

    if kind == "mineure":
        return formation.get("mineure", "")

    if kind == "date_obtention":
        return formation.get("date_obtention", "")

    return ""


def resolve_certification_field(profile: dict, ligne: int, colonne: int):
    certifications = profile.get("certifications", [])
    if ligne >= len(certifications):
        return ""
    champ = CERTIFICATION_COLUMN_MAP.get(colonne)
    if not champ:
        return ""
    return certifications[ligne].get(champ, "")

def resolve_field(candidates: list, profile: dict, input_type: str,
                   tag: str = "", available_options: list = None):

    # ── Interception prioritaire : champ téléphone sans label détecté ──
    # Évite qu'Ollama devine "prenom" ou une autre valeur au hasard
    # quand candidates=[] et input_type="tel".
    if input_type == "tel":
        telephone = profile.get("identite", {}).get("telephone", "") or \
                    profile.get("adresse", {}).get("telephone", "")
        if telephone:
            return telephone, "deterministic", "telephone", False
        return "", "deterministic", "telephone_absent", True

    repeated = detect_repeated_field(candidates)

    if repeated:
        groupe, ligne, colonne = repeated

        if groupe == 0:
            value = resolve_experience_field(profile, ligne, colonne)
            debug_key = f"experience[{ligne}].col{colonne}"
            if not value:
                return "", "deterministic", debug_key, True
            return value, "deterministic", debug_key, False

        if groupe == 1:
            value = resolve_formation_field(profile, ligne, candidates, tag, available_options)
            debug_key = f"formation[{ligne}]"
            if not value:
                return "", "deterministic", debug_key, True
            return value, "deterministic", debug_key, False

        if groupe == 2:
            value = resolve_certification_field(profile, ligne, colonne)
            debug_key = f"certification[{ligne}].col{colonne}"
            if not value:
                return "", "deterministic", debug_key, True
            return value, "deterministic", debug_key, False

    result = ask_ollama_for_field(
        candidates=candidates,
        profile=profile,
        input_type=input_type,
        available_options=available_options,
    )

    if result["skip"] or not result["value"]:
        return "", "ollama", result.get("key"), True

    return result["value"], "ollama", result.get("key"), False