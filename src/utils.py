import re
import unicodedata


def strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text or "")
        if unicodedata.category(c) != "Mn"
    )


def normalize(text: str) -> str:
    text = strip_accents(text or "")
    text = text.lower().strip()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def slugify(text: str) -> str:
    text = normalize(text)
    text = re.sub(r"[^a-z0-9 ]", "", text)
    return text.replace(" ", "_").strip("_")


def mask_value(value: str) -> str:
    value = str(value)
    if len(value) <= 2:
        return "*" * len(value)
    if "@" in value:
        parts = value.split("@", 1)
        left, domain = parts[0], parts[1]
        return left[:2] + "*" * max(1, len(left) - 2) + "@" + domain
    return value[:2] + "*" * max(1, len(value) - 2)


def safe_candidates(candidates: list) -> str:
    import json
    if not candidates:
        return "[]"
    return json.dumps(candidates, ensure_ascii=False)