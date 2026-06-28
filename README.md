# AutoFillAgent

Agent local Python qui remplit automatiquement des formulaires web à partir d'un fichier `data/data.json`,
avec reconnaissance intelligente des champs via alias locaux et fallback Ollama.

## Fonctionnalités

- Connexion à un Chromium ouvert via CDP (pas de nouveau navigateur lancé)
- Sélection interactive de l'onglet à remplir si plusieurs sont ouverts
- Reconnaissance des champs par alias locaux (nom, prénom, email, téléphone...)
- Fallback Ollama pour les champs ambigus ou inconnus
- Déduction de valeur par Ollama si le champ est vide dans `data/data.json`
- Gestion des checkboxes avec règles déterministes (`data/checkbox_rules.json`)
- Gestion des radios (civilité M./Mme)
- Gestion des `<select>` par label ou valeur
- 3 stratégies de clic pour les custom checkboxes (natif → label → JS force)
- Ajout automatique des nouvelles clés inconnues dans `data/data.json` pour complétion manuelle
- Rapport détaillé en fin d'exécution (remplis, ignorés, échecs, clés ajoutées)

## Arborescence

```text
Projet_IA_Automatique/
├── data/                  # Stockage des fichiers de données
│   ├── checkbox_rules.json
│   ├── config.json
│   └── data.json
├── src/                   # Code source principal
│   ├── browser.py         # Sélection de l'onglet CDP
│   ├── checkbox.py        # Logique des cases à cocher
│   ├── config.py          # Chargement de la configuration
│   ├── data_store.py      # Lecture/écriture data.json
│   ├── fields.py          # Détection et description des champs
│   ├── filler.py          # Remplissage des éléments
│   ├── __init__.py        
│   ├── ollama_utils.py    # Appels Ollama (clé et valeur)
│   ├── resolver.py        # Résolution clé → valeur
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

| Clé | Description |
| --- | --- |
| `debug_url` | URL CDP du Chromium ouvert |
| `auto_submit` | Soumettre automatiquement le formulaire après remplissage |
| `use_ollama` | Activer le fallback Ollama pour les champs ambigus |
| `ollama_model` | Modèle Ollama à utiliser (`ollama list` pour voir les disponibles) |
| `verbose` | Afficher les logs détaillés |

### `data/data.json`

Contient les données personnelles à injecter dans les formulaires.
Les clés inconnues découvertes lors du remplissage sont ajoutées automatiquement avec une valeur vide,
à compléter manuellement avant de relancer.

```json
{
  "known_data": {
    "prenom": "Jean",
    "nom": "Dupont",
    "email": "jean.dupont@mail.com",
    "telephone": "+33 7 89 56 24 25",
    "date_naissance": "04/05/1985",
    "adresse_ligne_1": "8 rue des lacs",
    "title": "Madame",
    "pays": "France"
  }
}

```

### `data/checkbox_rules.json`

Règles déterministes pour les cases à cocher, sans appel Ollama.
Édite ce fichier pour adapter le comportement selon tes préférences.

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

**Logique inversée :** certaines cases comme *"Je ne souhaite PAS recevoir"* doivent être cochées
pour refuser — ajoute leur texte dans `true_hints`.

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
  [0] [https://mon-espace.iledefrance-mobilites.fr/](https://mon-espace.iledefrance-mobilites.fr/)...
  [1] [https://career4.successfactors.com/](https://career4.successfactors.com/)...
Index : 0

```

## Fonctionnement détaillé

```text
Pour chaque champ input/textarea/select visible :
│
├── Skip ? (hidden, password, submit, captcha, antibot...) → ignoré
│
├── Checkbox ?
│   ├── Règles locales checkbox_rules.json → true/false
│   └── Fallback Ollama si aucune règle ne matche
│
├── Résolution de clé :
│   ├── Alias exact (FIELD_ALIASES)
│   ├── Alias partiel
│   ├── Ollama (mapping sémantique)
│   └── Slugification du label
│
├── Clé inconnue → ajout dans data.json (valeur vide)
│
├── Valeur vide → Ollama tente de déduire depuis les autres données
│   Ex: "nom complet" → "Jean Dupont" depuis prenom + nom
│
└── Remplissage :
    ├── <select> : select_option(label) puis select_option(value)
    ├── radio    : correspondance M./Mme
    └── texte    : fill()
        Checkbox : check/uncheck → clic label → JS force

```

## Champs reconnus nativement

| Clé | Alias reconnus |
| --- | --- |
| `prenom` | first name, firstname, prénom, forename... |
| `nom` | last name, lastname, surname, nom de famille... |
| `email` | email, e-mail, mail, courriel... |
| `telephone` | phone, mobile, tel, téléphone portable... |
| `adresse_ligne_1` | address, street, rue... |
| `ville` | city, town, ville... |
| `code_postal` | zip, postal code, code postal... |
| `pays` | country, pays... |
| `date_naissance` | date of birth, birthday, date de naissance... |
| `title` | civilité, salutation, mr, mme... |
| `societe` | company, organisation, société... |

Ajoute tes propres alias dans `src/resolver.py` → `FIELD_ALIASES`.

## Dépendances

```text
playwright>=1.53.0
ollama>=0.4.0

```

## Notes

* Le formulaire n'est **pas soumis automatiquement** par défaut (`auto_submit: false`)
* Les champs `password` sont toujours ignorés par sécurité
* Les tokens antibot/captcha sont détectés et ignorés automatiquement
* Garde un seul onglet utile ouvert si possible pour éviter la sélection manuelle
* Compatible avec les custom checkboxes (React, Vue, Angular...)

```


