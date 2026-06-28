import json
import ollama
from .config import log, USE_OLLAMA, OLLAMA_MODEL
from .utils import normalize, slugify


def ask_ollama_for_key(candidates: list, known_data: dict) -> str:
    if not USE_OLLAMA or not candidates:
        return "UNKNOWN"

    prompt = f"""Tu aides à remplir un formulaire web.

Clés disponibles dans known_data:
{list(known_data.keys())}

Textes trouvés pour ce champ de formulaire:
{candidates}

Règles:
- Réponds avec UNE seule clé snake_case.
- Si une clé existante correspond (même approximativement), retourne exactement cette clé.
  Ex: "nom de famille" → "nom", "numéro de téléphone" → "telephone"
- Si aucune clé ne correspond, propose une nouvelle clé snake_case courte et descriptive.
- Si le champ est technique (captcha, token, csrf, honeypot, robot, sécurité), réponds TECHNICAL_FIELD.
- Si tu ne peux vraiment pas déterminer, réponds UNKNOWN.
- N'ajoute aucun commentaire, juste la clé."""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response["message"]["content"].strip().replace("`", "")
        answer = answer.splitlines()[0].strip()
        answer = slugify(answer)
        return answer if answer else "UNKNOWN"
    except Exception as e:
        log(f"[OLLAMA][ERREUR] {e}")
        return "UNKNOWN"


def ask_ollama_for_value(candidates: list, key: str, known_data: dict, input_type: str = "text") -> str | None:
    if not USE_OLLAMA:
        return None

    known_str = json.dumps(known_data, ensure_ascii=False, indent=2)

    prompt = f"""Tu remplis un formulaire web.

Données connues sur la personne:
{known_str}

Le champ de formulaire a ces labels: {candidates}
La clé détectée pour ce champ est: "{key}"

Quelle valeur faut-il mettre dans ce champ?
- Utilise les données connues pour déduire la valeur, même si la clé n'est pas exactement présente.
  Ex: si le champ demande "nom complet" et que tu as "prenom"="Jean" et "nom"="Dupont", réponds "Jean Dupont".
- Si tu ne peux vraiment pas déduire la valeur, réponds uniquement: UNKNOWN
- Réponds uniquement avec la valeur brute, sans guillemets ni explication."""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response["message"]["content"].strip()
        answer = answer.splitlines()[0].strip().strip('"').strip("'")
        if not answer or normalize(answer) == "unknown":
            return None
        return answer
    except Exception as e:
        log(f"[OLLAMA][VALEUR][ERREUR] {e}")
        return None