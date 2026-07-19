"""
Resolver modulaire v6 :
- Ajoute la gestion déterministe du groupe 2 (attestations/certifications
  professionnelles type "ing." sur CN360), absent du profil -> skip propre
  au lieu de laisser Ollama deviner et halluciner du texte long dans les
  champs "Date de réception" ou "Si autre, veuillez préciser".
- Garde la logique v3 pour groupe 0 (expérience) et groupe 1 (formation).
- resolve_qa_bank_field devient sensible au type de champ (radio vs
  texte libre) pour choisir la bonne réponse dans reponses_frequentes,
  au lieu de laisser deux entrées concurrentes se marcher dessus.
"""
import re
from src.config import log
from src.ollama_utils import ask_ollama_for_field
from src.utils import normalize   # <- remonté en haut, plus au milieu du fichier

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

WORKDAY_EXPERIENCE_PATTERN = re.compile(r"workExperience-(\d+)--(\w+)")

WORKDAY_FIELD_MAP = {
    "jobTitle": "poste",
    "companyName": "entreprise",
    "location": "lieu",
    "roleDescription": "description",
}

_workday_block_order = {}
ADDRESS_LINE1_FIELD_NAMES = {
    "address", "address1", "address_line1", "street_address",
    "adresse", "adresse1", "streetaddress",
}


def resolve_address_line1_field(candidates: list, profile: dict) -> str:
    """
    Champs de type 'address' / 'address1' : ne renvoie QUE la ligne de
    rue (adresse.ligne_1). Évite qu'Ollama synthétise une adresse
    complète (rue + ville + pays) qui fait doublon avec les champs
    city/postcode/country généralement présents à côté.
    """
    for raw in candidates:
        norm = normalize(raw)
        if norm in ADDRESS_LINE1_FIELD_NAMES:
            return profile.get("adresse", {}).get("ligne_1", "")
    return None

def reset_workday_block_state():
    _workday_block_order.clear()


def detect_workday_experience_field(candidates: list):
    for raw in candidates:
        m = WORKDAY_EXPERIENCE_PATTERN.search(raw)
        if m:
            block_id, field_name = m.groups()
            if field_name in WORKDAY_FIELD_MAP:
                return block_id, field_name
    return None


def resolve_workday_experience_field(profile: dict, block_id: str, field_name: str):
    if block_id not in _workday_block_order:
        _workday_block_order[block_id] = len(_workday_block_order)
    ligne = _workday_block_order[block_id]

    experiences = profile.get("experiences", [])
    if ligne >= len(experiences):
        return ""

    champ = WORKDAY_FIELD_MAP[field_name]
    return experiences[ligne].get(champ, "")


def resolve_qa_bank_field(candidates: list, profile: dict, tag: str = "", input_type: str = ""):
    """
    Matche la question posée contre une banque de réponses fréquentes.
    Choisit la réponse "radio" (courte, Yes/No) ou "texte" (justification
    complète) selon le type réel du champ, pour éviter qu'une réponse
    longue soit envoyée à un bouton radio (qui ne matchera jamais) ou
    qu'un textarea reçoive juste "Yes" sans contexte.
    """
    text = normalize(" ".join(candidates))
    is_radio_like = input_type in {"radio", "checkbox"}

    for entry in profile.get("reponses_frequentes", []):
        for kw in entry.get("mots_cles", []):
            if normalize(kw) in text:
                if is_radio_like:
                    return entry.get("reponse_radio", entry.get("reponse", ""))
                return entry.get("reponse_texte", entry.get("reponse", ""))
    return None


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
    if ligne >= len(formations):
        return ""
    formation = formations[ligne]
    kind = classify_formation_field(candidates)

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

    if input_type == "tel":
        telephone = profile.get("identite", {}).get("telephone", "") or \
                    profile.get("adresse", {}).get("telephone", "")
        if telephone:
            return telephone, "deterministic", "telephone", False
        return "", "deterministic", "telephone_absent", True

    workday_match = detect_workday_experience_field(candidates)
    if workday_match:
        block_id, field_name = workday_match
        value = resolve_workday_experience_field(profile, block_id, field_name)
        debug_key = f"workday_experience[{block_id}].{field_name}"
        if not value:
            return "", "deterministic", debug_key, True
        return value, "deterministic", debug_key, False
    address_match = resolve_address_line1_field(candidates, profile)
    if address_match is not None:
        debug_key = "adresse.ligne_1"
        if not address_match:
            return "", "deterministic", debug_key, True
        return address_match, "deterministic", debug_key, False
    qa_match = resolve_qa_bank_field(candidates, profile, tag=tag, input_type=input_type)
    if qa_match is not None:
        debug_key = "qa_bank"
        if not qa_match:
            return "", "deterministic", debug_key, True
        return qa_match, "deterministic", debug_key, False

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