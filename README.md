# IDENT - SIED V1.0

Application bureau Python + pywebview pour la gestion des assurés, collectivités et référentiels.

---

# Guide utilisateur (README USER)

## Démarrage
1. Lancez l’application (EXE ou `run_ident.bat`).
2. Connectez‑vous avec votre **identifiant** et **mot de passe**.
3. La page d’accueil affiche les modules : **Assurés**, **Collectivités**, **Référentiel**.

## Navigation
- **Barre d’outils** : logo, recherche globale (accueil), boutons navigation, thème, menu utilisateur.
- **Bouton Home (maison)** : retour à l’accueil.
- **Menu utilisateur** : informations de l’utilisateur connecté + déconnexion.

## Recherche globale (accueil)
La barre de recherche permet de retrouver un **assuré** ou une **collectivité**.

## Module Collectivités
Fonctions principales :
- Recherche de collectivités.
- Consultation des détails (Identification, Adresse, Responsables, Assurés, Communautés, Référent, Export).
- Consultation d’un assuré depuis l’onglet Assurés de la collectivité.

## Module Assurés
Fonctions principales :
- Recherche par NIR / nom / prénoms.
- Consultation détaillée (Infos personnelles, Situations, Maladie, Vieillesse, RCO, CSG, Adresse, Ayant droit, ARPEGE selon profil).
- Export Excel complet des onglets.

## Export Excel
Depuis l’écran d’export, vous pouvez :
- Exporter dans le dossier réseau correspondant au **service**.
- Choisir un dossier personnalisé.
Pour **SIED**, le choix de dossier est plus large (AFF, PCI, JUR, RET, SIED + perso).

## Astuces
- Si un module reste affiché après retour Home, cliquez sur **Home** pour réinitialiser l’état.
- Si un export échoue, vérifiez le réseau et vos droits sur le dossier.

---

# Guide développeur (README DEV)

## Stack technique
- **Python** + **pywebview** (UI HTML/CSS/JS dans une fenêtre native).
- **Oracle DB** via `oracledb`.
- **Excel** via `openpyxl`.
- **Build** via **PyInstaller**.

## Arborescence
```
.
├─ app.py                     # Point d’entrée + API JS
├─ services/
│  └─ oracle_client.py         # Accès Oracle + requêtes + exports
├─ templates/                  # HTML (login, home, modules, etc.)
├─ static/                     # CSS, assets UI
├─ images/                     # Logos / icônes
├─ requirements.txt
├─ run_ident.bat               # Lancement local (venv + Oracle)
└─ MonApp.spec                 # Build PyInstaller
```

## Architecture
- **pywebview** charge `templates/login.html` puis la navigation se fait via JS.
- **app.py** expose des fonctions Python appelées depuis JS (webview API).
- **oracle_client.py** centralise les requêtes Oracle + mapping des résultats.
- **templates/** contient les vues HTML pour chaque écran.
- **static/style.css** contient le design global.

## Données & sessions
- Les infos utilisateur connecté sont récupérées en DB puis stockées côté app.
- Les écrans utilisent `localStorage` pour conserver un contexte (ex. assuré consulté).
- Le retour Home doit réinitialiser l’état (ex: NIR ciblé, collectivité ciblée).

## Développement local
```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Ou via `run_ident.bat`.

## Build Windows (PyInstaller)
Commande recommandée :
```
.\.venv\Scripts\python.exe -m PyInstaller app.py ^
  --onedir ^
  --clean ^
  --noupx ^
  --noconfirm ^
  --name MonApp ^
  --version-file version.txt ^
  --icon "images\logo.ico" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "images;images" ^
  --collect-all oracledb
```

Résultat : `dist\MonApp\MonApp.exe`

## Problèmes connus
- **Antivirus** : certains agents (ex. SentinelOne) bloquent l’EXE.
  - Éviter `--onefile`.
  - Préférer `--onedir`.
  - Ajouter une exception côté sécurité si possible.
- **Ressources manquantes** : vérifier `--add-data` pour templates/static/images.

## Maintenance
Bonnes pratiques :
- Centraliser les requêtes SQL dans `oracle_client.py`.
- Revoir les sélecteurs HTML/CSS avant tout changement UI.
- Tester chaque module après modification (collectivités, assurés, référentiel).
- Rebuild après chaque grosse modification UI ou export.

## Contribution
1. Modifier le code.
2. Tester en local.
3. Rebuild si nécessaire.
4. Commit + push.
