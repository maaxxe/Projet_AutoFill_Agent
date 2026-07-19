from .config import log
from .utils import normalize
from .date_utils import format_date_for_field
import re
import time

FILLER_VERSION = "2026-07-v6-dates-auto-format"
log(f"[VERSION] src/filler.py chargé — {FILLER_VERSION}")


def value_alternatives(value: str) -> list:
    raw = str(value).strip()
    parts = re.split(r"\s+ou\s+|[,/;|]", raw, flags=re.IGNORECASE)
    alternatives = [raw] + [p.strip() for p in parts if p.strip()]

    deduped, seen = [], set()
    for alt in alternatives:
        if alt and alt not in seen:
            seen.add(alt)
            deduped.append(alt)
    return deduped

def handle_radio_group(el, key: str, value: str, candidates: list):
    val = normalize(str(value))
    text = normalize(" ".join(candidates))

    match_label = None
    if any(x in text for x in ["monsieur", "mr", "m."]) and val in {"m", "mr", "monsieur", "m."}:
        match_label = "monsieur"
    elif any(x in text for x in ["madame", "mme", "mrs"]) and val in {"mme", "madame", "mrs"}:
        match_label = "madame"
    elif val and val in text:
        match_label = "generic_match"

    if not match_label:
        return False, "radio_skip_no_match"

    # Stratégie 1 : check() standard
    try:
        el.check(timeout=3000)
        if el.is_checked():
            return True, f"radio_check({match_label})"
    except Exception:
        pass

    # Stratégie 2 : clic forcé (contourne les checks de visibilité Playwright)
    try:
        el.click(force=True, timeout=3000)
        if el.is_checked():
            return True, f"radio_click_force({match_label})"
    except Exception:
        pass

    # Stratégie 3 : clic sur le label/wrapper associé (radios custom-stylés)
    try:
        clicked = el.evaluate("""(input) => {
            const id = input.getAttribute('id');
            if (id) {
                const label = document.querySelector('label[for="' + id + '"]');
                if (label) { label.click(); return 'label[for]'; }
            }
            const parentLabel = input.closest('label');
            if (parentLabel) { parentLabel.click(); return 'parent_label'; }
            const next = input.nextElementSibling;
            if (next) { next.click(); return 'next_sibling'; }
            return 'none';
        }""")
        if el.is_checked():
            return True, f"radio_label_click({clicked})({match_label})"
    except Exception:
        pass

    # Stratégie 4 : forçage JS pur, dernier recours
    try:
        el.evaluate("""(e) => {
            e.checked = true;
            e.dispatchEvent(new Event('input', {bubbles: true}));
            e.dispatchEvent(new Event('change', {bubbles: true}));
            e.dispatchEvent(new Event('click', {bubbles: true}));
        }""")
        return True, f"radio_js_force({match_label})"
    except Exception as e:
        return False, f"radio_check_failed: {e}"

def fill_element(el, value: str) -> tuple[bool, str]:
    tag = el.evaluate("e => e.tagName.toLowerCase()")
    input_type = (el.get_attribute("type") or "").lower()

    # ── Conversion automatique de date vers le format attendu par le champ ──
    pattern_attr = el.get_attribute("pattern") or ""
    placeholder = el.get_attribute("placeholder") or ""
    value = format_date_for_field(
        value,
        input_type=input_type,
        pattern_attr=pattern_attr,
        placeholder=placeholder,
    )

    if tag == "select":
        alternatives = value_alternatives(value)

        real_options = []
        deadline = time.time() + 4
        while time.time() < deadline:
            try:
                options = el.evaluate("""
                    (select) => Array.from(select.options).map(o => ({
                        value: o.value,
                        label: (o.textContent || '').trim()
                    }))
                """)
            except Exception as e:
                return False, f"select_failed: impossible de lire les options ({e})"

            real_options = [o for o in options if o["label"] or o["value"]]
            if len(real_options) > 1:
                break
            time.sleep(0.3)

        if not real_options:
            return False, "select_failed: aucune option chargée dans ce menu (widget pas encore peuplé)"

        for alt in alternatives:
            alt_norm = normalize(alt)
            for o in real_options:
                if normalize(o["label"]) == alt_norm or normalize(o["value"]) == alt_norm:
                    try:
                        el.select_option(label=o["label"], timeout=3000)
                        return True, f"select_option(label={o['label']!r})"
                    except Exception:
                        try:
                            el.select_option(value=o["value"], timeout=3000)
                            return True, f"select_option(value={o['value']!r})"
                        except Exception as e:
                            return False, f"select_failed_apres_match: {e}"

        for alt in alternatives:
            alt_norm = normalize(alt)
            for o in real_options:
                label_norm = normalize(o["label"])
                if alt_norm and (alt_norm in label_norm or label_norm in alt_norm):
                    try:
                        el.select_option(label=o["label"], timeout=3000)
                        return True, f"select_option(fuzzy_label={o['label']!r})"
                    except Exception:
                        continue

        available = [o["label"] for o in real_options if o["label"]][:20]
        return False, (f"select_failed: aucune valeur parmi {alternatives} ne correspond. "
                        f"Options disponibles: {available}")

    if input_type in {"checkbox", "radio"}:
        wanted = normalize(value) in {"1", "true", "yes", "oui", "on"}
        try:
            before = el.is_checked()

            if before == wanted:
                return True, f"already_{'checked' if wanted else 'unchecked'}()"

            if wanted:
                el.check()
            else:
                el.uncheck()
            after = el.is_checked()
            if after == wanted:
                return True, f"{'check' if wanted else 'uncheck'}(before={before} after={after})"

            clicked = el.evaluate("""(input) => {
                const id = input.getAttribute('id');
                if (id) {
                    const label = document.querySelector('label[for="' + id + '"]');
                    if (label) { label.click(); return 'label[for]'; }
                }
                const parentLabel = input.closest('label');
                if (parentLabel) { parentLabel.click(); return 'parent_label'; }
                const next = input.nextElementSibling;
                if (next) { next.click(); return 'next_sibling'; }
                const prev = input.previousElementSibling;
                if (prev) { prev.click(); return 'prev_sibling'; }
                return 'none';
            }""")
            after2 = el.is_checked()
            if after2 == wanted:
                return True, f"label_click({clicked})(before={before} after={after2})"

            el.evaluate(f"""(e) => {{
                e.checked = {'true' if wanted else 'false'};
                e.dispatchEvent(new Event('change', {{bubbles: true}}));
                e.dispatchEvent(new Event('input', {{bubbles: true}}));
                e.dispatchEvent(new Event('click', {{bubbles: true}}));
            }}""")
            after3 = el.is_checked()
            return True, f"js_force(before={before} after={after3})"

        except Exception as e:
            return False, f"check_failed: {e}"

    try:
        el.fill(str(value))
        return True, "fill()"
    except Exception as e:
        return False, f"fill_failed: {e}"