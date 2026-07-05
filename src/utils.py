import re
import unicodedata


def normalize(text: str) -> str:
    if not text:
        return ""
    text = str(text).lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def slugify(text: str) -> str:
    n = normalize(text)
    return re.sub(r"\s+", "_", n).strip("_")


def mask_value(value: str) -> str:
    s = str(value)
    if len(s) <= 4:
        return "*" * len(s)
    visible = max(2, len(s) // 4)
    return s[:visible] + "*" * (len(s) - visible)


def safe_candidates(candidates: list, limit: int = 6) -> list:
    return candidates[:limit]