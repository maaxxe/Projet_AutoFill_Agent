from .config import log
from .utils import normalize

TECHNICAL_HINTS = [
    "captcha", "token", "csrf", "antibot", "honeypot",
    "validate", "validation", "robot", "security", "answer",
]

SKIP_TYPES = {"hidden", "submit", "button", "reset", "file", "image", "password"}


def candidate_texts(page, el) -> list:
    texts = []
    for attr in ["name", "id", "placeholder", "aria-label"]:
        value = el.get_attribute(attr) or ""
        if value.strip():
            texts.append(value.strip())

    try:
        labels = el.evaluate("""
            (node) => {
                const labels = [];
                if (node.labels) {
                    for (const l of node.labels) labels.push(l.innerText || l.textContent || '');
                }
                if (!labels.length) {
                    const id = node.getAttribute('id');
                    if (id) {
                        const direct = document.querySelector(`label[for="${id}"]`);
                        if (direct) labels.push(direct.innerText || direct.textContent || '');
                    }
                    const wrapper = node.closest('label');
                    if (wrapper) labels.push(wrapper.innerText || wrapper.textContent || '');
                }
                return labels.filter(Boolean);
            }
        """)
        texts.extend([t.strip() for t in labels if t and t.strip()])
    except Exception:
        pass

    # NOUVEAU : texte de la question portée par un <fieldset><legend> ou
    # un conteneur role="group"/aria-labelledby (cas Workable/Greenhouse
    # pour les groupes de radios YES/NO sans label direct sur l'input).
    try:
        group_texts = el.evaluate("""
            (node) => {
                const texts = [];
                const fieldset = node.closest('fieldset');
                if (fieldset) {
                    const legend = fieldset.querySelector('legend');
                    if (legend) texts.push(legend.innerText || legend.textContent || '');
                }
                const group = node.closest('[role="group"], [role="radiogroup"], .form-field, [class*="question"]');
                if (group) {
                    const labelledBy = group.getAttribute('aria-labelledby');
                    if (labelledBy) {
                        for (const id of labelledBy.split(' ')) {
                            const target = document.getElementById(id);
                            if (target) texts.push(target.innerText || target.textContent || '');
                        }
                    }
                    const heading = group.querySelector('legend, [class*="question"], label:not([for])');
                    if (heading && heading !== node) texts.push(heading.innerText || heading.textContent || '');
                }
                return texts.filter(Boolean);
            }
        """)
        texts.extend([t.strip() for t in group_texts if t and t.strip()])
    except Exception:
        pass

    try:
        described = el.get_attribute("aria-describedby") or ""
        for eid in described.split():
            helper = page.locator(f"#{eid}")
            if helper.count() > 0:
                text = helper.first.inner_text().strip()
                if text:
                    texts.append(text)
    except Exception:
        pass

    deduped, seen = [], set()
    for t in texts:
        n = normalize(t)
        if n and n not in seen:
            seen.add(n)
            deduped.append(t)
    return deduped

def describe_element(el) -> dict:
    return {
        "tag": el.evaluate("e => e.tagName.toLowerCase()"),
        "type": (el.get_attribute("type") or "").lower(),
        "name": el.get_attribute("name") or "",
        "id": el.get_attribute("id") or "",
        "placeholder": el.get_attribute("placeholder") or "",
    }


def get_select_options(el) -> list:
    """
    NOUVEAU : extrait les libellés des options d'un <select>, pour les
    fournir à Ollama et lui permettre de choisir une valeur qui existe
    réellement dans le menu, plutôt que de deviner un texte libre qui
    n'y figure jamais (ex: "Usherbrooke" absent d'un menu de provinces).
    """
    try:
        options = el.evaluate("""
            (select) => Array.from(select.options).map(o => (o.textContent || '').trim())
        """)
        return [o for o in options if o]
    except Exception:
        return []


def should_skip(el, candidates=None) -> bool:
    input_type = (el.get_attribute("type") or "").lower()
    if input_type in SKIP_TYPES:
        return True

    name = normalize(el.get_attribute("name") or "")
    field_id = normalize(el.get_attribute("id") or "")
    text = normalize(" ".join(candidates or []))

    if any(h in name or h in field_id or h in text for h in TECHNICAL_HINTS):
        return True

    try:
        if not el.is_visible() or not el.is_enabled():
            return True
    except Exception:
        return True

    return False