# AutoFillAgent

Agent local Python qui remplit automatiquement des formulaires web à partir d'un profil structuré `data/profile.json`, avec résolution déterministe des blocs répétés (expériences, formations, certifications), auto-détection du format de date accepté par chaque champ, et fallback Ollama pour les champs ambigus ou hors structure connue.

## Fonctionnalités

- Connexion à un Chromium ouvert via CDP (pas de nouveau navigateur lancé)
- Sélection interactive de l'onglet à remplir si plusieurs sont ouverts
- Résolution **déterministe** des blocs de champs répétés type ATS (Cornerstone/CSOD) : expériences (`groupe 0`), formations (`groupe 1`), certifications/attestations (`groupe 2`)
- Fallback Ollama uniquement pour les champs hors structure connue (adresse, ville, pays...), avec un profil allégé **sans jamais transmettre de texte long type résumé de carrière**
- Garde-fou anti-hallucination : toute réponse Ollama de plus de 120 caractères est rejetée
- **Auto-détection empirique du format de date** : plusieurs formats sont testés directement dans le DOM (fill + relecture + `checkValidity()`) jusqu'à trouver celui accepté par le site, au lieu de deviner un format unique à l'aveugle
- Respect de la précision de la date source (année seule, année-mois, ou date complète) : jamais de jour ou de mois inventé pour compléter une donnée partielle
- Gestion des `<select>` fermés (listes d'institutions/programmes) via sélection automatique de l'option "Autre" quand la valeur réelle du profil n'existe pas dans la liste
- Gestion des checkboxes avec règles déterministes (`data/checkbox_rules.json`)
- Gestion des radios (civilité M./Mme)
- 3 stratégies de clic pour les custom checkboxes (natif → label → JS force)
- Rapport détaillé en fin d'exécution (remplis, ignorés, échecs, clés ajoutées)

## Arborescence

```text
Projet_IA_Automatique/
├── data/                  # Stockage des fichiers de données
│   ├── checkbox_rules.json
│   ├── config.json
│   └── profile.json       # Profil structuré (identite, adresse, experiences, formations, certifications)
├── src/                   # Code source principal
│   ├── browser.py         # Sélection de l'onglet CDP
│   ├── checkbox.py        # Logique des cases à cocher
│   ├── config.py          # Chargement de la configuration
│   ├── data_store.py      # Lecture/écriture profile.json
│   ├── date_utils.py      # Détection + essai empirique multi-format des dates
│   ├── fields.py          # Détection et description des champs
│   ├── filler.py          # Remplissage des éléments (dates, select, checkbox, texte)
│   ├── __init__.py
│   ├── ollama_utils.py    # Appels Ollama (profil allégé, garde-fou anti-hallucination)
│   ├── resolver.py        # Résolution déterministe des blocs répétés + fallback Ollama
│   └── utils.py           # normalize, slugify, mask...
├── main.py                # Point d'entrée principal
├── requirements.txt
└── README.md
```

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Configuration

### `data/config.json`

```json
{
  "debug_url": "http://localhost:9222",
  "auto_submit": false,
  "use_ollama": true,
  "ollama_model": "qwen2.5-coder:14b",
  "verbose": true
}
```

| Clé            | Description                                                          |
| -------------- | ---------------------------------------------------------------------|
| `debug_url`    | URL CDP du Chromium ouvert                                           |
| `auto_submit`  | Soumettre automatiquement le formulaire après remplissage            |
| `use_ollama`   | Activer le fallback Ollama pour les champs ambigus                   |
| `ollama_model` | Modèle Ollama à utiliser (`ollama list` pour voir les disponibles)   |
| `verbose`      | Afficher les logs détaillés                                          |

### `data/profile.json`

Contient le profil structuré injecté dans les formulaires. Les blocs répétés (expériences, formations, certifications) sont résolus **par position de ligne**, sans jamais passer par Ollama, ce qui élimine les hallucinations et les répétitions de valeurs entre lignes.

```json
{
  "identite": {
    "prenom": "Jean",
    "nom": "Dupont",
    "email": "jean.dupont@mail.com",
    "telephone": "+33 7 89 56 24 25"
  },
  "adresse": {
    "ligne_1": "8 rue des lacs",
    "ville": "Paris",
    "departement": "Île-de-France",
    "code_postal": "75000",
    "pays": "France"
  },
  "experiences": [
    {
      "poste": "Stage ingénieur systèmes embarqués",
      "entreprise": "Isybot",
      "date_debut": "2025-06",
      "date_fin": "2025-09"
    }
  ],
  "formations": [
    {
      "institution": "Université de Sherbrooke",
      "programme": "Maîtrise",
      "majeure": "Intelligence artificielle",
      "mineure": "",
      "date_obtention": "2027"
    }
  ],
  "certifications": [],
  "langues": ["Français", "Anglais"],
  "preferences_candidature": {}
}
```

**Format des dates :** stocke toujours au format ISO (`AAAA`, `AAAA-MM` ou `AAAA-MM-JJ`) selon la précision réelle connue. C'est `date_utils.py` qui se charge de convertir vers le format attendu par chaque champ du site cible — ne préformate jamais une date dans `profile.json`.

### `data/checkbox_rules.json`

Règles déterministes pour les cases à cocher, sans appel Ollama. Édite ce fichier pour adapter le comportement selon tes préférences.

```json
{
  "false_hints": [
    "newsletter", "marketing", "offres commerciales",
    "receive new job", "hear more about", "career opportunit"
  ],
  "true_hints": [
    "souhaite conserver mon numero",
    "ne souhaite pas recevoir",
    "cgu", "conditions generales", "terms and conditions"
  ]
}
```

**Priorité :** `false_hints` est évalué en premier. Si aucune règle ne matche, Ollama décide.

**Logique inversée :** certaines cases comme *"Je ne souhaite PAS recevoir"* doivent être cochées pour refuser — ajoute leur texte dans `true_hints`.

## Lancement

**Terminal 1 — Ollama**

```bash
ollama serve
```

**Terminal 2 — Chromium**

```bash
chromium --remote-debugging-port=9222
```

Ouvre ensuite la page du formulaire dans ce Chromium.

**Terminal 3 — AutoFillAgent**

```bash
source .venv/bin/activate
python main.py
```

Si plusieurs onglets sont ouverts, le script demande lequel utiliser :

```
Plusieurs onglets détectés. Choisissez l'index :
  [0] https://mon-espace.iledefrance-mobilites.fr/...
  [1] https://career4.successfactors.com/...
Index : 0
```

## Fonctionnement détaillé

```text
Pour chaque champ input/textarea/select visible :
│
├── Skip ? (file, checkbox FAQ, hidden, password, submit, captcha, antibot...) → ignoré
│
├── Checkbox ?
│   ├── Règles locales checkbox_rules.json → true/false
│   └── Fallback Ollama si aucune règle ne matche
│
├── Champ identifié comme bloc répété (id de type "$resume-field_G_L_C") ?
│   ├── Groupe 0 (expériences)    → resolve_experience_field(ligne, colonne)
│   ├── Groupe 1 (formations)     → resolve_formation_field(ligne, candidates, tag, options)
│   │     └── Select "Institution*"/"Programme*" fermé → sélection auto de "Autre" si la
│   │         vraie valeur du profil n'existe pas dans les options disponibles
│   └── Groupe 2 (certifications) → resolve_certification_field(ligne, colonne)
│         └── Profil sans section certifications → bloc entier skip, aucun appel Ollama
│
├── Sinon → résolution via Ollama (profil allégé, sans texte long, garde-fou 120 caractères)
│
├── Valeur reconnue comme date ISO probable (input type="date" OU motif AAAA[-MM[-JJ]]) ?
│   └── fill_date_with_autodetect() : essaie plusieurs formats dans le DOM réel
│         (JJ/MM/AAAA, AAAA-MM-JJ, MM/JJ/AAAA, MM/AAAA, AAAA seule, etc.)
│         jusqu'à trouver celui accepté (valeur relue non vide + checkValidity() OK)
│
└── Remplissage :
    ├── <select> : select_option(label) → select_option(value) → fuzzy_label → "Autre"
    ├── radio    : correspondance M./Mme
    ├── date     : essai multi-format empirique (voir ci-dessus)
    └── texte    : fill()
        Checkbox : check/uncheck → clic label → JS force
```

## Résolution des blocs répétés (expériences / formations / certifications)

Les sites ATS type Cornerstone (CSOD) génèrent des champs avec des identifiants du type `$resume-field_0_2_1` où :

- Le **1er chiffre** est le groupe (0 = expérience, 1 = formation, 2 = certification)
- Le **2e chiffre** est la ligne (index de l'entrée dans la liste du profil)
- Le **3e chiffre** est la colonne (poste/entreprise/date, ou institution/programme/majeure...)

Cette structure permet un mapping déterministe direct vers `profile.json`, sans jamais solliciter Ollama pour ces champs — ce qui élimine les répétitions de valeurs entre lignes et les hallucinations de texte long dans les petits champs (dates, sigles, codes).

## Auto-détection du format de date

Plutôt que d'imposer un format unique, `date_utils.py` teste plusieurs formats candidats directement dans le champ du navigateur, dans cet ordre de priorité :

1. Format imposé par `<input type="date">` (toujours `AAAA-MM-JJ`)
2. Format déduit de l'attribut `pattern` ou du `placeholder` du champ (ex: "JJ/MM/AAAA")
3. Liste de formats courants testés successivement, adaptée à la précision de la donnée source (année seule, année-mois, ou date complète)

Chaque essai est validé par relecture de `input_value()` et `checkValidity()` avant d'être retenu. Les logs affichent `[DATE_AUTODETECT] valeur=... → format retenu=...` pour tracer quel format a été accepté par le site.

## Dépendances

```text
playwright>=1.53.0
ollama>=0.4.0
requests>=2.31.0
```

## Notes

- Le formulaire n'est **pas soumis automatiquement** par défaut (`auto_submit: false`)
- Les champs `password` et `file` sont toujours ignorés par sécurité
- Les tokens antibot/captcha sont détectés et ignorés automatiquement
- Ollama ne reçoit jamais de texte long type résumé de carrière : uniquement identité, adresse, langues et préférences de candidature, pour éviter toute hallucination
- Garde un seul onglet utile ouvert si possible pour éviter la sélection manuelle
- Compatible avec les custom checkboxes (React, Vue, Angular...)
- Supprime `src/__pycache__` après toute mise à jour des fichiers `.py` pour éviter de charger une version en cache