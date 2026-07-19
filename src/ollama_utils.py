"""
ollama_utils.py v4 :
- context_profile envoyé à Ollama = profil complet MOINS "resume_profil"
  (le seul champ texte libre à risque). Avant, TOUT (experiences,
  formations, competences...) était retiré -> le modèle inventait des
  intitulés de poste / entreprises sur les champs non couverts par le
  système de blocs répétés (ex: formulaires Workday).
- format = JSON Schema contraint (decoding contraint côté Ollama) ->
  plus besoin de regex fragile pour extraire le JSON.
- Ajout d'un champ "reasoning" dans le JSON -> force un raisonnement
  court avant la décision finale (équivalent CoT), et donne un log
  exploitable en cas d'erreur.
- Garde-fou anti-hallucination : la valeur renvoyée doit être traçable
  dans le profil réel, sinon rejet automatique.
"""
import json
import requests

from src.config import OLLAMA_URL, OLLAMA_MODEL, OLLAMA_OPTIONS, log
from src.utils import normalize

OLLAMA_TIMEOUT = 60

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "reasoning": {"type": "string"},
        "key": {"type": "string"},
        "value": {"type": "string"},
        "skip": {"type": "boolean"},
    },
    "required": ["reasoning", "key", "value", "skip"],
}

EXCLUDED_PROFILE_KEYS = {"resume_profil"}  # blobs de texte libre à ne jamais injecter tels quels


def _call_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": RESPONSE_SCHEMA,
                "options": OLLAMA_OPTIONS,
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        log(f"[OLLAMA][ERREUR] {e}")
        return ""


def _build_context_profile(profile: dict) -> dict:
    return {k: v for k, v in profile.items() if k not in EXCLUDED_PROFILE_KEYS}


def _value_is_grounded(value: str, profile: dict) -> bool:
    """
    Vérifie que la valeur n'est pas inventée. Tolère les valeurs
    composées à partir de plusieurs champs réels (ex: adresse =
    ville + departement + pays), en comparant mot à mot plutôt
    qu'en cherchant la phrase entière comme sous-chaîne exacte.
    """
    if not value:
        return True
    haystack = normalize(json.dumps(profile, ensure_ascii=False))
    value_norm = normalize(value)

    if len(value_norm) <= 3:
        return True
    if value_norm in haystack:
        return True

    tokens = [t for t in value_norm.split() if len(t) > 2]
    if not tokens:
        return True
    matched = sum(1 for t in tokens if t in haystack)
    return (matched / len(tokens)) >= 0.8

def ask_ollama_for_field(candidates: list, profile: dict, input_type: str,
                          block_row: tuple = None, available_options: list = None):
    context_profile = _build_context_profile(profile)
    candidates_text = " | ".join(candidates) if candidates else "(aucun label détecté)"

    options_context = ""
    if available_options:
        options_context = f"\nOptions disponibles dans ce menu déroulant : {available_options}"

    prompt = f"""Tu remplis un champ de formulaire de candidature à partir de ce profil JSON :

{json.dumps(context_profile, ensure_ascii=False)}

Champ à remplir :
- Labels détectés : {candidates_text}
- Type HTML : {input_type}
{options_context}

Avant de répondre, raisonne étape par étape dans le champ "reasoning" :
1. Que désigne précisément ce champ (poste, entreprise, date, compétence, choix de liste...) ?
2. Quelle section précise du profil JSON ci-dessus correspond exactement à ce champ ?
3. Cette section existe-t-elle réellement dans le JSON fourni ? Si non -> skip obligatoire.
4. Si c'est un menu déroulant, la valeur choisie existe-t-elle mot pour mot (ou quasi) dans les options listées ?

Règles strictes et non négociables :
- N'utilise QUE les données explicitement présentes dans le profil JSON ci-dessus.
- N'invente JAMAIS une valeur qui ne provient pas littéralement du profil.
- Si aucune donnée précise du profil ne correspond, "skip" doit être true et "value" une chaîne vide.
- Si c'est un menu déroulant, choisis une valeur qui existe dans les options listées, sinon skip=true.

Réponds strictement selon le schéma JSON demandé.
"""

    raw = _call_ollama(prompt)
    try:
        parsed = json.loads(raw)
    except Exception as e:
        log(f"[OLLAMA][PARSE_ERROR] {e} | raw={raw[:200]!r}")
        return {"key": None, "value": "", "skip": True}

    value = str(parsed.get("value", "")).strip()
    skip = bool(parsed.get("skip", False))

    if len(value) > 120:
        log(f"[OLLAMA][GUARD] valeur suspecte rejetée (trop longue): {value[:60]!r}...")
        return {"key": parsed.get("key"), "value": "", "skip": True}

    if not skip and not _value_is_grounded(value, context_profile):
        log(f"[OLLAMA][GUARD] valeur non traçable dans le profil, rejetée: {value!r} "
            f"| reasoning={parsed.get('reasoning', '')[:150]!r}")
        return {"key": parsed.get("key"), "value": "", "skip": True}

    return {"key": parsed.get("key"), "value": value, "skip": skip}