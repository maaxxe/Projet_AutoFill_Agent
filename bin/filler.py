from config import log
from utils import normalize


def handle_radio_group(el, key: str, value: str, candidates: list):
    if key == "title":
        val  = normalize(str(value))
        text = normalize(" ".join(candidates))
        if any(x in text for x in ["monsieur", "mr", "m."]):
            if val in {"m", "mr", "monsieur", "m."}:
                el.check()
                return True, "radio_check(monsieur)"
        if any(x in text for x in ["madame", "mme", "mrs"]):
            if val in {"mme", "madame", "mrs"}:
                el.check()
                return True, "radio_check(madame)"
        return False, "radio_skip_no_match"
    return False, "radio_skip"


def fill_element(el, value: str) -> tuple[bool, str]:
    tag        = el.evaluate("e => e.tagName.toLowerCase()")
    input_type = (el.get_attribute("type") or "").lower()

    if tag == "select":
        try:
            el.select_option(label=value)
            return True, "select_option(label)"
        except Exception:
            try:
                el.select_option(value=value)
                return True, "select_option(value)"
            except Exception as e:
                return False, f"select_failed: {e}"

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

            # Essai 2 : clic sur label associé
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

            # Essai 3 : JS force
            el.evaluate(f"""(e) => {{
                e.checked = {'true' if wanted else 'false'};
                e.dispatchEvent(new Event('change', {{bubbles: true}}));
                e.dispatchEvent(new Event('input',  {{bubbles: true}}));
                e.dispatchEvent(new Event('click',  {{bubbles: true}}));
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