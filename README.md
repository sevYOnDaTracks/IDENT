# IDENT - SIED V1.0 (Python + pywebview)

Application de bureau minimale : Python ouvre une fenêtre native qui rend une page HTML/CSS moderne (écran d'accueil avec 3 boutons).

## Prérequis
- Python 3.10+
- `pip`

## Installation
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement
- Option recommandée : double-cliquer `run_ident.bat` (utilise l'environnement `.venv` et ajoute l'instant client si présent).
- En ligne de commande :
```bash
.\.venv\Scripts\activate
python app.py
```
Une fenêtre « IDENT - SIED V1.0 » s'ouvre (pywebview) avec l'IHM HTML/CSS embarquée. Fermez la fenêtre pour quitter.

## Structure
- `app.py` : point d'entrée Python (pywebview) + API JS.
- `services/oracle_client.py` : client Oracle (requêtes, export Excel).
- `templates/index.html` : page HTML de l'interface.
- `static/style.css` : styles modernes.
- `requirements.txt` : dépendances Python.
