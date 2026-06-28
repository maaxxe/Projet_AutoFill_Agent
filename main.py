from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from src.config import DEBUG_URL, AUTO_SUBMIT, log
from src.data_store import load_data, save_data
from src.browser import pick_page
from src.fields import candidate_texts, describe_element, should_skip
from src.resolver import resolve_key
from src.filler import fill_element, handle_radio_group
from src.checkbox import decide_checkbox
from src.ollama_utils import ask_ollama_for_value
from src.utils import mask_value, safe_candidates


def main():
    data       = load_data()
    known_data = data.setdefault("known_data", {})

    added_keys  = []
    filled      = []
    unresolved  = []
    skipped     = []
    empty_known = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(DEBUG_URL)
        if not browser.contexts:
            raise RuntimeError("Aucun contexte navigateur trouvé via CDP.")

        context = browser.contexts[0]
        page    = pick_page(context)
        page.wait_for_load_state("domcontentloaded")

        locator = page.locator("input, textarea, select")
        count   = locator.count()

        print("=== DÉBUT ANALYSE FORMULAIRE ===")
        print(f"Page   : {page.url}")
        print(f"Champs : {count}\n")

        for i in range(count):
            el         = locator.nth(i)
            candidates = candidate_texts(page, el)
            desc       = describe_element(el)
            input_type = desc["type"]

            if should_skip(el, candidates):
                skipped.append({"index": i, "reason": "skip_rule", "desc": desc, "candidates": candidates})
                log(f"[SKIP #{i}] {desc} | candidates={safe_candidates(candidates)}")
                continue

            # ── Checkbox ──────────────────────────────────────────────────────
            if input_type == "checkbox":
                value   = decide_checkbox(candidates)
                log(f"[CHECKBOX #{i}] candidates={safe_candidates(candidates)} → {value}")
                success, action = fill_element(el, value)
                entry = {"index": i, "key": "checkbox", "source": "checkbox_engine",
                         "value": value, "masked_value": value, "action": action,
                         "desc": desc, "candidates": candidates}
                if success:
                    filled.append(entry)
                    log(f"[FILLED CHECKBOX #{i}] value={value} action={action}\n")
                else:
                    unresolved.append({**entry, "reason": action})
                    log(f"[FAILED CHECKBOX #{i}] reason={action}\n")
                continue

            # ── Autres champs ─────────────────────────────────────────────────
            key, value, source = resolve_key(candidates, known_data)

            log(f"[FIELD #{i}] {desc}")
            log(f"           candidates={safe_candidates(candidates)}")
            log(f"           resolved_key={key} | source={source}")

            if not key:
                unresolved.append({"index": i, "reason": "no_key", "desc": desc, "candidates": candidates})
                log(f"[UNRESOLVED #{i}] aucune clé trouvée\n")
                continue

            if key not in known_data:
                known_data[key] = ""
                added_keys.append({"index": i, "key": key, "source": source, "desc": desc, "candidates": candidates})
                save_data(data)
                log(f"[NEW KEY #{i}] ajout de '{key}' dans data.json\n")
                continue

            if value in (None, ""):
                log(f"[EMPTY VALUE #{i}] clé='{key}' vide, tentative Ollama...")
                ollama_value = ask_ollama_for_value(candidates, key, known_data, input_type=input_type)
                if ollama_value:
                    value  = ollama_value
                    source = "ollama_deduced"
                    log(f"[OLLAMA DEDUCED #{i}] key={key} → '{value}'")
                else:
                    empty_known.append({"index": i, "key": key, "source": source, "desc": desc, "candidates": candidates})
                    log(f"[EMPTY VALUE #{i}] Ollama n'a pas pu déduire pour '{key}'\n")
                    continue

            if input_type == "radio":
                if not known_data.get(key):
                    unresolved.append({"index": i, "reason": "empty_radio_value", "key": key,
                                       "desc": desc, "candidates": candidates})
                    log(f"[EMPTY RADIO #{i}] aucune valeur connue pour '{key}'\n")
                    continue
                success, action = handle_radio_group(el, key, value, candidates)
                entry = {"index": i, "key": key, "source": source, "value": value,
                         "masked_value": mask_value(value), "action": action,
                         "desc": desc, "candidates": candidates}
                if success:
                    filled.append(entry)
                    log(f"[FILLED RADIO #{i}] key={key} | value={value} | action={action}\n")
                else:
                    unresolved.append({**entry, "reason": action})
                    log(f"[FAILED RADIO #{i}] key={key} | reason={action}\n")
                continue

            success, action = fill_element(el, value)
            entry = {"index": i, "key": key, "source": source, "value": value,
                     "masked_value": mask_value(value), "action": action,
                     "desc": desc, "candidates": candidates}
            if success:
                filled.append(entry)
                log(f"[FILLED #{i}] key={key} | value={mask_value(value)} | action={action}\n")
            else:
                unresolved.append({**entry, "reason": action})
                log(f"[FAILED #{i}] key={key} | reason={action}\n")

        save_data(data)

        # ── Rapport ───────────────────────────────────────────────────────────
        if filled:
            print("\n--- CHAMPS REMPLIS ---")
            for item in filled:
                print(f"- #{item['index']} key={item['key']} value={item['masked_value']} "
                      f"source={item['source']} action={item['action']}")
        if added_keys:
            print("\n--- CLÉS AJOUTÉES AU JSON (à compléter manuellement) ---")
            for item in added_keys:
                print(f"- #{item['index']} key={item['key']} source={item['source']} "
                      f"candidates={safe_candidates(item['candidates'])}")
        if empty_known:
            print("\n--- CLÉS CONNUES MAIS VIDES ---")
            for item in empty_known:
                print(f"- #{item['index']} key={item['key']} "
                      f"candidates={safe_candidates(item['candidates'])}")
        if unresolved:
            print("\n--- CHAMPS NON RÉSOLUS / ÉCHECS ---")
            for item in unresolved[:50]:
                print(f"- #{item['index']} reason={item.get('reason')} key={item.get('key')} "
                      f"candidates={safe_candidates(item['candidates'])}")
        if skipped:
            print("\n--- CHAMPS IGNORÉS ---")
            for item in skipped[:50]:
                print(f"- #{item['index']} reason={item['reason']} desc={item['desc']}")

        if AUTO_SUBMIT:
            try:
                page.locator("button[type='submit'], input[type='submit']").first.click(timeout=2000)
            except PlaywrightTimeoutError:
                pass

        browser.close()


if __name__ == "__main__":
    main()