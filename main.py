"""
main.py v4 : passe le tag HTML (input/select) au resolver pour permettre
la logique spéciale "Autre" sur les select fermés d'institution/programme.
Réinitialise l'état du resolver Workday à chaque nouvelle page traitée.
"""
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from src.config import DEBUG_URL, AUTO_SUBMIT, log
from src.data_store import load_profile
from src.browser import pick_page
from src.fields import candidate_texts, describe_element, should_skip, get_select_options
from src.resolver import resolve_field, reset_workday_block_state
from src.filler import fill_element, handle_radio_group
from src.checkbox import decide_checkbox
from src.utils import mask_value, safe_candidates


def main():
    profile = load_profile()

    filled = []
    unresolved = []
    skipped = []

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(DEBUG_URL)
        if not browser.contexts:
            raise RuntimeError("Aucun contexte navigateur trouvé via CDP.")

        context = browser.contexts[0]
        page = pick_page(context)
        page.wait_for_load_state("domcontentloaded")

        # Nouvelle page -> nouveau formulaire -> le mapping bloc Workday
        # (block_id -> index d'expérience) ne doit pas hériter d'une page précédente.
        reset_workday_block_state()

        locator = page.locator("input, textarea, select")
        count = locator.count()

        print("=== DÉBUT ANALYSE FORMULAIRE (mode modulaire / Ollama) ===")
        print(f"Page   : {page.url}")
        print(f"Champs : {count}\n")

                

        for i in range(count):
                    try:
                        el = locator.nth(i)
                        candidates = candidate_texts(page, el)
                        desc = describe_element(el)
                        input_type = desc["type"]
                        tag = desc["tag"]

                        if should_skip(el, candidates):
                            skipped.append({"index": i, "reason": "skip_rule", "desc": desc, "candidates": candidates})
                            log(f"[SKIP #{i}] {desc} | candidates={safe_candidates(candidates)}")
                            continue

                        if input_type == "checkbox":
                            value = decide_checkbox(candidates)
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

                        available_options = None
                        if tag == "select":
                            available_options = get_select_options(el)

                        value, source, debug_key, skip = resolve_field(
                            candidates, profile, input_type, tag=tag, available_options=available_options
                        )

                        log(f"[FIELD #{i}] {desc}")
                        log(f"           candidates={safe_candidates(candidates)}")
                        log(f"           key(debug)={debug_key} | source={source} | skip={skip}")

                        if skip or not value:
                            unresolved.append({"index": i, "reason": f"{source}_no_match", "desc": desc, "candidates": candidates})
                            log(f"[UNRESOLVED #{i}] Aucune correspondance trouvée\n")
                            continue

                        if input_type == "radio":
                            success, action = handle_radio_group(el, debug_key or "radio", value, candidates)
                            entry = {"index": i, "key": debug_key, "source": source, "value": value,
                                    "masked_value": mask_value(value), "action": action,
                                    "desc": desc, "candidates": candidates}
                            if success:
                                filled.append(entry)
                                log(f"[FILLED RADIO #{i}] value={value} | action={action}\n")
                            else:
                                unresolved.append({**entry, "reason": action})
                                log(f"[FAILED RADIO #{i}] reason={action}\n")
                            continue

                        success, action = fill_element(el, value)
                        entry = {"index": i, "key": debug_key, "source": source, "value": value,
                                "masked_value": mask_value(value), "action": action,
                                "desc": desc, "candidates": candidates}
                        if success:
                            filled.append(entry)
                            log(f"[FILLED #{i}] key={debug_key} | value={mask_value(value)} | action={action}\n")
                        else:
                            unresolved.append({**entry, "reason": action})
                            log(f"[FAILED #{i}] key={debug_key} | reason={action}\n")

                    except Exception as e:
                        unresolved.append({"index": i, "reason": f"unexpected_error: {e}",
                                            "desc": {}, "candidates": []})
                        log(f"[ERROR #{i}] Exception non gérée, champ ignoré : {e}\n")
                        continue

        if filled:
            print("\n--- CHAMPS REMPLIS ---")
            for item in filled:
                print(f"- #{item['index']} key={item['key']} value={item['masked_value']} "
                      f"action={item['action']}")
        if unresolved:
            print("\n--- CHAMPS NON RÉSOLUS / ÉCHECS ---")
            for item in unresolved[:50]:
                print(f"- #{item['index']} reason={item.get('reason')} "
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