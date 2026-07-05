def pick_page(context):
    """
    Sélectionne l'onglet actif à traiter parmi ceux ouverts dans le
    contexte navigateur connecté via CDP.
    """
    pages = context.pages
    if not pages:
        raise RuntimeError("Aucun onglet ouvert trouvé.")

    if len(pages) == 1:
        return pages[0]

    print("\n=== ONGLETS DÉTECTÉS ===")
    for i, p in enumerate(pages):
        print(f"[{i}] {p.url}")

    print("\nPlusieurs onglets détectés. Choisissez l'index :")
    for i, p in enumerate(pages):
        print(f"  [{i}] {p.url}")

    idx = int(input("Index : ").strip())
    chosen = pages[idx]
    print(f"\n[ONGLET SÉLECTIONNÉ] {chosen.url}")
    return chosen