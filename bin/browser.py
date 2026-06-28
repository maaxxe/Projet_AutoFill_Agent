from config import log


def pick_page(context):
    pages = context.pages

    print("\n=== ONGLETS DÉTECTÉS ===")
    for i, p in enumerate(pages):
        print(f"[{i}] {p.url}")

    web_pages = [p for p in pages if (p.url or "").startswith(("http://", "https://"))]

    if len(web_pages) == 1:
        chosen = web_pages[0]
        print(f"\n[ONGLET SÉLECTIONNÉ] {chosen.url}\n")
        return chosen

    if len(web_pages) > 1:
        print("\nPlusieurs onglets détectés. Choisissez l'index :")
        for i, p in enumerate(web_pages):
            print(f"  [{i}] {p.url}")
        while True:
            try:
                choice = int(input("Index : ").strip())
                if 0 <= choice < len(web_pages):
                    chosen = web_pages[choice]
                    print(f"\n[ONGLET SÉLECTIONNÉ] {chosen.url}\n")
                    return chosen
                print(f"Entrez un nombre entre 0 et {len(web_pages) - 1}")
            except ValueError:
                print("Entrez un nombre entier.")

    visible_pages = [p for p in pages if p.url and p.url != "about:blank"]
    chosen = visible_pages[0] if visible_pages else pages[0]
    print(f"\n[ONGLET SÉLECTIONNÉ PAR DÉFAUT] {chosen.url}\n")
    return chosen