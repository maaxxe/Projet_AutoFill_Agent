"""
date_utils.py v4 : essai empirique multi-format dans le DOM.
Ce fichier ne doit importer QUE des modules standards (re, datetime).
Aucun import de src.date_utils ici -> évite le circular import.
"""
import re
from datetime import datetime

ISO_DATE_PATTERN = re.compile(r"^(19|20)\d{2}(-\d{2}(-\d{2})?)?$")

PLACEHOLDER_FORMAT_HINTS = [
    (re.compile(r"jj/mm/aaaa", re.IGNORECASE), "%d/%m/%Y"),
    (re.compile(r"dd/mm/yyyy", re.IGNORECASE), "%d/%m/%Y"),
    (re.compile(r"mm/dd/yyyy", re.IGNORECASE), "%m/%d/%Y"),
    (re.compile(r"mm/yyyy", re.IGNORECASE), "%m/%Y"),
    (re.compile(r"yyyy-mm-dd", re.IGNORECASE), "%Y-%m-%d"),
    (re.compile(r"aaaa-mm-jj", re.IGNORECASE), "%Y-%m-%d"),
    (re.compile(r"yyyy", re.IGNORECASE), "%Y"),
]

CANDIDATE_FORMATS_DAY = [
    "%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y",
    "%Y/%m/%d", "%d.%m.%Y", "%d/%m/%y", "%m-%d-%Y",
]
CANDIDATE_FORMATS_MONTH = ["%m/%Y", "%Y-%m", "%Y/%m", "%m-%Y"]
CANDIDATE_FORMATS_YEAR = ["%Y", "%y"]


def is_probable_iso_date(raw_value: str) -> bool:
    return bool(ISO_DATE_PATTERN.match(str(raw_value).strip()))


def _precision(raw_value: str) -> str:
    parts = str(raw_value).strip().split("-")
    if len(parts) >= 3:
        return "day"
    if len(parts) == 2:
        return "month"
    return "year"


def parse_iso_date(raw_value: str):
    raw_value = str(raw_value).strip()
    if not is_probable_iso_date(raw_value):
        return None
    parts = raw_value.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) >= 2 else 1
    day = int(parts[2]) if len(parts) >= 3 else 1
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def detect_target_format(input_type: str, pattern_attr: str, placeholder: str) -> str:
    if input_type == "date":
        return "%Y-%m-%d"
    if pattern_attr:
        digits_groups = re.findall(r"\d\{(\d)\}", pattern_attr)
        if digits_groups == ["2", "2", "4"]:
            return "%d/%m/%Y"
        if digits_groups == ["4", "2", "2"]:
            return "%Y-%m-%d"
        if digits_groups == ["2", "4"]:
            return "%m/%Y"
    if placeholder:
        for regex, fmt in PLACEHOLDER_FORMAT_HINTS:
            if regex.search(placeholder):
                return fmt
    return ""


def candidate_formats_for(precision: str, detected_format: str = "") -> list:
    base = {
        "day": CANDIDATE_FORMATS_DAY,
        "month": CANDIDATE_FORMATS_MONTH,
        "year": CANDIDATE_FORMATS_YEAR,
    }.get(precision, CANDIDATE_FORMATS_DAY)

    if detected_format and detected_format in base:
        ordered = [detected_format] + [f for f in base if f != detected_format]
    elif detected_format:
        ordered = [detected_format] + base
    else:
        ordered = list(base)
    return ordered


def format_date_for_field(raw_value: str, input_type: str = "",
                           pattern_attr: str = "", placeholder: str = "") -> str:
    parsed = parse_iso_date(raw_value)
    if parsed is None:
        return raw_value
    precision = _precision(raw_value)
    target_format = detect_target_format(input_type, pattern_attr, placeholder)
    fmt = target_format or candidate_formats_for(precision)[0]
    try:
        return parsed.strftime(fmt)
    except ValueError:
        return raw_value


def fill_date_with_autodetect(el, raw_value: str, input_type: str = "",
                               pattern_attr: str = "", placeholder: str = "") -> tuple:
    parsed = parse_iso_date(raw_value)
    if parsed is None:
        return False, "", "not_a_date"

    precision = _precision(raw_value)
    detected_format = detect_target_format(input_type, pattern_attr, placeholder)
    formats_to_try = candidate_formats_for(precision, detected_format)

    for fmt in formats_to_try:
        try:
            candidate_value = parsed.strftime(fmt)
        except ValueError:
            continue

        try:
            el.fill("")
            el.fill(candidate_value)
            el.evaluate("(e) => { e.dispatchEvent(new Event('input', {bubbles:true})); "
                        "e.dispatchEvent(new Event('change', {bubbles:true})); "
                        "e.dispatchEvent(new Event('blur', {bubbles:true})); }")

            actual_value = el.input_value()
            is_valid = el.evaluate("(e) => e.checkValidity ? e.checkValidity() : true")

            if actual_value.strip() and is_valid:
                return True, fmt, f"fill_autodetect(format={fmt!r})"
        except Exception:
            continue

    return False, "", "all_formats_rejected"