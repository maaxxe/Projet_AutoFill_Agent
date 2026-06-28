from src.utils import normalize, slugify
from src.config import log
from src.ollama_utils import ask_ollama_for_key

FIELD_ALIASES = {
    "prenom":          ["prenom", "prénom", "first name", "firstname", "given name", "forename"],
    "nom":             ["nom", "last name", "lastname", "surname", "family name", "nom de famille"],
    "email":           ["email", "e-mail", "mail", "courriel"],
    "telephone":       ["telephone", "téléphone", "phone", "mobile", "cell", "cellphone", "tel",
                        "numéro de téléphone", "numero de telephone", "téléphone portable", "telephone portable"],
    "adresse":         ["adresse", "address", "street", "address line 1", "address1"],
    "adresse_ligne_2": ["address line 2", "address2", "apt", "apartment", "suite", "complement adresse"],
    "adresse_ligne_1": ["adresse ligne 1", "adresse 1", "rue"],
    "ville":           ["ville", "city", "town"],
    "code_postal":     ["code postal", "postal code", "zip", "zip code"],
    "pays":            ["pays", "country"],
    "societe":         ["societe", "société", "company", "organisation", "organization"],
    "date_naissance":  ["date naissance", "date de naissance", "birth date", "date of birth", "birthday"],
    "title":           ["civilite", "civilité", "title", "salutation", "mr", "mrs", "mme", "m."],
}


def build_alias_index() -> dict:
    index = {}
    for canonical, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            index[normalize(alias)] = canonical
    return index


ALIAS_INDEX = build_alias_index()


def resolve_key(candidates: list, known_data: dict):
    for raw in candidates:
        norm = normalize(raw)
        if norm in ALIAS_INDEX:
            key = ALIAS_INDEX[norm]
            return key, known_data.get(key, ""), "alias_exact"

    for raw in candidates:
        norm = normalize(raw)
        for alias, canonical in ALIAS_INDEX.items():
            if alias and alias in norm:
                return canonical, known_data.get(canonical, ""), "alias_partial"

    ollama_key = ask_ollama_for_key(candidates, known_data)
    if ollama_key == "TECHNICAL_FIELD":
        return None, "", "technical_field"
    if ollama_key != "UNKNOWN":
        return ollama_key, known_data.get(ollama_key, ""), "ollama"

    for raw in candidates:
        generated = slugify(raw)
        if generated:
            return generated, known_data.get(generated, ""), "slugified"

    return None, "", "none"