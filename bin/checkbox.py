import json
from pathlib import Path
import ollama
from config import log, USE_OLLAMA, OLLAMA_MODEL
from utils import normalize

_rules = json.loads(Path("checkbox_rules.json").read_text(encoding="utf-8"))
FALSE_HINTS = _rules["false_hints"]
TRUE_HINTS  = _rules["true_hints"]


def classify_checkbox_local(candidates: list) -> str | None:
    text = normalize(" ".join(candidates))

    for hint in FALSE_HINTS:
        if hint in text:
            log(f"[CHECKBOX][LOCAL] hint='{hint}' → false")
            return "false"

    for hint in TRUE_HINTS:
        if hint in text:
            log(f"[CHECKBOX][LOCAL] hint='{hint}' → true")
            return "true"

    return None


def ask_ollama_checkbox(candidates: list) -> str:
    if not USE_OLLAMA:
        return "false"

    prompt = f"""Tu remplis un formulaire web. Réponds UNIQUEMENT par le mot "true" ou le mot "false", rien d'autre.

Label de la case à cocher:
{candidates}

- "true" = cocher (CGU obligatoires, conserver données utiles, refuser marketing)
- "false" = ne pas cocher (newsletter, offres commerciales, notifications emploi)

Réponds uniquement: true ou false"""

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        answer = response["message"]["content"].strip().lower()
        answer = answer.splitlines()[0].strip().strip('"').strip("'")
        log(f"[CHECKBOX][OLLAMA] réponse brute: {answer!r}")
        if "true" in answer:
            return "true"
        if "false" in answer:
            return "false"
        return "false"
    except Exception as e:
        log(f"[CHECKBOX][OLLAMA][ERREUR] {e}")
        return "false"


def decide_checkbox(candidates: list) -> str:
    local = classify_checkbox_local(candidates)
    if local is not None:
        return local
    return ask_ollama_checkbox(candidates)