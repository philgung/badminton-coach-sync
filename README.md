# 🏸 Badminton Super Coach — Notion to AI Skill

Ce projet synchronise automatiquement vos notes, exercices et schémas tactiques de badminton depuis **Notion** vers un fichier `output/skills.md` prêt à être utilisé dans **Claude** (Projects / Claude Code) et **Gemini** (Gems).

## 📁 Arborescence du projet

```text
badminton-coach-sync/
├── .github/
│   └── workflows/
│       └── sync-coach.yml   # Action GitHub pour mettre à jour le fichier en 1 clic
├── output/
│   └── skills.md            # Fichier généré (ignoré au début, créé à la 1ère synchro)
├── .env.example             # Modèle des variables d'environnement
├── .gitignore               # Fichiers exclus de Git (dont .env)
├── README.md                # Documentation
├── requirements.txt         # Dépendances Python
└── sync_coach.py            # Script principal d'extraction Notion -> Markdown
```

## 🚀 Installation & Utilisation

### 1. Configuration Notion
1. Créez une intégration sur [notion.so/my-integrations](https://www.notion.so/my-integrations) avec les droits de lecture (*Read content*).
2. Récupérez le **Secret Token** (`ntn_...`).
3. Sur votre page Notion principale "Badminton", cliquez sur `•••` > **Connexions** > ajoutez votre intégration.
4. Récupérez l'**ID de la page** dans son URL (les 32 caractères à la fin de l'URL).

### 2. Utilisation en local
```bash
# Cloner le repo
git clone https://github.com/votre-user/badminton-coach-sync.git
cd badminton-coach-sync

# Créer l'environnement virtuel et installer les dépendances
python -m venv venv
source venv/bin/activate  # Sur Windows : venv\Scripts\activate
pip install -r requirements.txt

# Configurer les secrets
cp .env.example .env
# -> Éditez .env avec votre NOTION_TOKEN et NOTION_PAGE_ID

# Lancer la génération à la demande
python sync_coach.py
```

### 3. Mise à jour à la demande directement depuis GitHub (Sans terminal)
Grâce au fichier `.github/workflows/sync-coach.yml` inclus :
1. Sur votre dépôt GitHub, allez dans **Settings > Secrets and variables > Actions**.
2. Ajoutez deux secrets : `NOTION_TOKEN` et `NOTION_PAGE_ID`.
3. Dès que vous modifiez vos notes dans Notion, allez dans l'onglet **Actions** de GitHub > **Update Badminton Coach Skill** > cliquez sur **Run workflow**.
4. Votre fichier `output/skills.md` est automatiquement mis à jour dans le dépôt !

## 🤖 Importer dans Claude ou Gemini
- **Claude Code :** Placez `skills.md` dans `.claude/skills/badminton-coach/SKILL.md`.
- **Claude.ai (Projects) :** Créez un projet "Coach Badminton" et ajoutez `output/skills.md` dans *Project Knowledge*.
- **Gemini (Gems) :** Créez un Gem "Coach Badminton" et importez `output/skills.md` dans ses fichiers de connaissances.
