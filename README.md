
# AutoFillAgent

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
  // URL de connexion CDP au navigateur Chromium ouvert
  "debug_url": "http://localhost:9222",

  // Passe à true pour valider automatiquement le formulaire en fin de script
  "auto_submit": false,

  // Active l'appel à l'IA locale pour déduire les champs non gérés par les règles déterministes
  "use_ollama": true,

  // Le modèle à exécuter. Privilégier un modèle code plutôt qu'un modèle chat
  "ollama_model": "qwen2.5-coder:14b",

  // Affiche les logs d'exécution détaillés dans le terminal
  "verbose": true,

  // Taille du contexte envoyé à l'IA. À augmenter si le formulaire contient des menus déroulants immenses
  "num_ctx": 8192,

  // Nombre maximum de tokens (mots) que l'IA est autorisée à générer en réponse
  "num_predict": 500
}
```

| Clé             | Description                                                                                                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `debug_url`    | URL CDP du Chromium ouvert                                                                                                                                                                                           |
| `auto_submit`  | Soumettre automatiquement le formulaire après remplissage                                                                                                                                                           |
| `use_ollama`   | Activer le fallback Ollama pour les champs ambigus                                                                                                                                                                   |
| `ollama_model` | Modèle Ollama à utiliser (`ollama list` pour voir les disponibles) — préférer un modèle orienté code/instructions strictes plutôt qu'un généraliste, pour une meilleure adhérence aux consignes de skip |
| `verbose`      | Afficher les logs détaillés                                                                                                                                                                                        |
| `num_ctx`      | Taille du contexte Ollama — à augmenter si les menus déroulants transmis sont longs                                                                                                                               |
| `num_predict`  | Nombre max de tokens de sortie — laisse de la marge au champ`reasoning` avant le JSON final                                                                                                                       |

Ce fichier est désormais réellement lu par `src/config.py` (fusionné avec des valeurs de repli si une clé manque) : plus de décalage possible entre ce que tu configures ici et ce qui est effectivement utilisé.

### `data/profil.json`

Contient le profil structuré injecté dans les formulaires. Les blocs répétés (expériences, formations, certifications) sont résolus **par position de ligne**, sans jamais passer par Ollama pour les sites au format `groupe_ligne_colonne` ; les formulaires Workday sont résolus par un mapping séquentiel dédié.

```json
{
  "identite": {
    "prenom": "[PRENOM]",
    "nom": "[NOM]",
    "email": "[EMAIL]@domaine.com",
    "telephone": "+33 6 00 00 00 00"
  },
  "adresse": {
    "ligne_1": "123 rue de l'Exemple",
    "ville": "[VILLE]",
    "departement": "[REGION]",
    "code_postal": "00000",
    "pays": "[PAYS]"
  },
  "experiences": [
    {
      "poste": "[INTITULE DU POSTE]",
      "entreprise": "[NOM DE L'ENTREPRISE]",
      "lieu": "[VILLE, PAYS]",
      "date_debut": "2025-01",
      "date_fin": "2025-06",
      "description": "..."
    }
  ],
  "formations": [
    {
      "institution": "[NOM DE L'ETABLISSEMENT]",
      "programme": "[NIVEAU D'ETUDE/DIPLOME]",
      "majeure": "[SPECIALITE]",
      "mineure": "",
      "date_obtention": "2027"
    }
  ],
  "certifications": [],
  "competences": {},
  "langues": ["Français", "Anglais"],
  "preferences_candidature": {},
  "reponses_frequentes": [
    {
      "mots_cles": ["salary expectation", "pretention salariale", "expected salary"],
      "reponse_texte": "A discuter selon le poste, les responsabilites et les avantages proposes",
      "reponse_radio": ""
    },
    {
      "mots_cles": ["communication skills in both english and french", "fluent in english and french"],
      "reponse_radio": "Yes",
      "reponse_texte": "Oui : francais langue maternelle, anglais courant, espagnol intermediaire"
    }
  ]
}

```

**Format des dates :** stocke toujours au format ISO (`AAAA`, `AAAA-MM` ou `AAAA-MM-JJ`) selon la précision réelle connue. C'est `date_utils.py` qui se charge de convertir vers le format attendu par chaque champ du site cible — ne préformate jamais une date dans `profil.json`.

**`reponses_frequentes` :** une seule entrée par question, avec `reponse_radio` (courte, pour matcher un bouton YES/NO) **et** `reponse_texte` (justification complète, pour un `textarea`/champ libre). Ne jamais dupliquer les mêmes mots-clés sur deux entrées différentes — seule la première rencontrée dans la liste est utilisée, ce qui rend le comportement imprévisible si deux entrées se recoupent.

### `data/checkbox_rules.json`

Règles déterministes pour les cases à cocher, sans appel Ollama.

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

**Priorité :** `false_hints` est évalué en premier. Si aucune règle ne matche, la case reste décochée par défaut (prudence RGPD/marketing).

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
  [0] [https://recrutement.entreprise-exemple.fr/](https://recrutement.entreprise-exemple.fr/)...
  [1] [https://career.site-ats-exemple.com/](https://career.site-ats-exemple.com/)...
Index : 0

```

## Fonctionnement détaillé

```text
Pour chaque champ input/textarea/select visible (erreur isolée par champ,
jamais fatale pour le reste du formulaire) :
│
├── Skip ? (file, hidden, password, submit, captcha, antibot...) → ignoré
│
├── Checkbox ?
│   ├── Règles locales checkbox_rules.json (false_hints puis true_hints) → true/false
│   └── Défaut : ne pas cocher
│
├── Type "tel" ? → téléphone du profil, déterministe
│
├── Champ Workday (id "workExperience-N--champ") ?
│   └── Mapping séquentiel bloc → ligne d'expérience, déterministe
│
├── Champ "address"/"address1"/... ?
│   └── Ligne de rue uniquement (adresse.ligne_1), déterministe
│
├── Question connue de reponses_frequentes (mots-clés matchés) ?
│   └── reponse_radio si radio/checkbox, sinon reponse_texte
│
├── Champ identifié comme bloc répété type CN360 (id "$resume-field_G_L_C") ?
│   ├── Groupe 0 (expériences)    → resolve_experience_field(ligne, colonne)
│   ├── Groupe 1 (formations)     → resolve_formation_field(ligne, candidates, tag, options)
│   │     └── Select "Institution*"/"Programme*" fermé → sélection auto de "Autre" si la
│   │         vraie valeur du profil n'existe pas dans les options disponibles
│   └── Groupe 2 (certifications) → resolve_certification_field(ligne, colonne)
│         └── Profil sans section certifications → bloc entier skip, aucun appel Ollama
│
├── Sinon → résolution via Ollama :
│   ├── profil complet (hors blobs de texte libre) + labels + options du menu si <select>
│   ├── raisonnement court demandé (champ "reasoning") avant la décision finale
│   ├── sortie contrainte par JSON Schema (plus de parsing regex fragile)
│   └── garde-fou : valeur rejetée si non traçable dans le profil réel, ou si > 120 caractères
│
├── Valeur reconnue comme date ISO probable (input type="date" OU motif AAAA[-MM[-JJ]]) ?
│   └── fill_date_with_autodetect() : essaie plusieurs formats dans le DOM réel
│         (JJ/MM/AAAA, AAAA-MM-JJ, MM/JJ/AAAA, MM/AAAA, AAAA seule, etc.)
│         jusqu'à trouver celui accepté (valeur relue non vide + checkValidity() OK)
│
└── Remplissage :
    ├── <select> : select_option(label) → select_option(value) → fuzzy_label → "Autre"
    ├── radio    : check() → clic forcé → clic label/wrapper → forçage JS
    ├── date     : essai multi-format empirique (voir ci-dessus)
    └── texte    : fill()
        Checkbox : check/uncheck → clic label → JS force

```

## Résolution des blocs répétés (expériences / formations / certifications)

Les sites ATS type Cornerstone (CSOD) génèrent des champs avec des identifiants du type `$resume-field_0_2_1` où :

* Le **1er chiffre** est le groupe (0 = expérience, 1 = formation, 2 = certification)
* Le **2e chiffre** est la ligne (index de l'entrée dans la liste du profil)
* Le **3e chiffre** est la colonne (poste/entreprise/date, ou institution/programme/majeure...)

Cette structure permet un mapping déterministe direct vers `profil.json`, sans jamais solliciter Ollama pour ces champs — ce qui élimine les répétitions de valeurs entre lignes et les hallucinations de texte long dans les petits champs (dates, sigles, codes).

## Résolution dédiée Workday

Workday nomme ses champs d'expérience `workExperience-N--jobTitle`, `workExperience-N--companyName`, etc., où `N` est un identifiant de bloc DOM (pas un index séquentiel fiable). Le resolver associe chaque nouveau `N` rencontré à la ligne suivante de `profile["experiences"]`, dans l'ordre d'apparition à l'écran — ce mapping est réinitialisé à chaque nouvelle page (`reset_workday_block_state()`) pour ne pas contaminer une candidature suivante dans la même session.

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

* Le formulaire n'est **pas soumis automatiquement** par défaut (`auto_submit: false`)
* Les champs `password` et `file` sont toujours ignorés par sécurité
* Les tokens antibot/captcha sont détectés et ignorés automatiquement
* Ollama reçoit le profil complet (hors blobs de texte libre type résumé de carrière) : lui retirer des données réelles produit des hallucinations sur les champs qui en ont besoin, d'où l'importance du garde-fou de traçabilité plutôt que de la privation de contexte
* Une exception sur un champ (widget custom, timeout, iframe) est loguée et n'interrompt jamais le reste du formulaire
* Garde un seul onglet utile ouvert si possible pour éviter la sélection manuelle
* Compatible avec les custom checkboxes/radios (React, Vue, Angular...) grâce aux 4 stratégies de repli
* Supprime `src/__pycache__` après toute mise à jour des fichiers `.py` pour éviter de charger une version en cache

```

```
