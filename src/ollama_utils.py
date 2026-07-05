"""
ollama_utils.py v3 : retire définitivement "resume_profil" du profil léger
envoyé à Ollama. C'était la cause du bug répété où le LLM comblait tout
champ non identifié avec ce texte long, y compris les dates et attestations.

Ollama ne reçoit plus QUE des données structurées ponctuelles (identite,
adresse, langues, preferences_candidature). S'il ne trouve rien dans ces
sections précises, il DOIT renvoyer skip=true plutôt que d'improviser.
"""
import json
import re
import requests

from src.config import OLLAMA_URL, OLLAMA_MODEL, log

OLLAMA_TIMEOUT = 60


def _call_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=OLLAMA_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except Exception as e:
        log(f"[OLLAMA][ERREUR] {e}")
        return ""


def ask_ollama_for_field(candidates: list, profile: dict, input_type: str,
                          block_row: tuple = None, available_options: list = None):
    light_profile = {
        "identite": profile.get("identite", {}),
        "adresse": profile.get("adresse", {}),
        "langues": profile.get("langues", []),
        "preferences_candidature": profile.get("preferences_candidature", {}),
    }

    candidates_text = " | ".join(candidates) if candidates else "(aucun label détecté)"

    options_context = ""
    if available_options:
        options_context = f"\nOptions disponibles dans ce menu déroulant : {available_options}"

    prompt = f"""Tu remplis un champ de formulaire de candidature à partir de ce profil :

{json.dumps(light_profile, ensure_ascii=False)}

Champ à remplir :
- Labels détectés : {candidates_text}
- Type HTML : {input_type}
{options_context}

Règles strictes et non négociables :
- N'utilise QUE les données explicitement présentes dans le profil ci-dessus.
- N'invente JAMAIS de texte, ne réutilise JAMAIS une longue description dans un petit champ (date, code, nom, sigle).
- Si aucune donnée précise du profil ne correspond à ce champ, réponds skip=true. C'est le comportement attendu par défaut.
- Si c'est un menu déroulant, choisis une valeur qui existe dans les options listées, sinon skip=true.

Réponds uniquement par un JSON strict, sans texte autour :
{{"key": "nom_libre_debug", "value": "valeur à insérer", "skip": false}}
"""

    raw = _call_ollama(prompt)
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return {"key": None, "value": "", "skip": True}
        parsed = json.loads(match.group(0))
        value = str(parsed.get("value", "")).strip()

        if len(value) > 120:
            log(f"[OLLAMA][GUARD] valeur suspecte rejetée (trop longue): {value[:60]!r}...")
            return {"key": parsed.get("key"), "value": "", "skip": True}

        return {
            "key": parsed.get("key"),
            "value": value,
            "skip": bool(parsed.get("skip", False)),
        }
    except Exception as e:
        log(f"[OLLAMA][PARSE_ERROR] {e} | raw={raw[:200]!r}")
        return {"key": None, "value": "", "skip": True}