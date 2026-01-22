import sys
from pathlib import Path
from typing import Dict, Optional

import webview


def _bootstrap_site_packages() -> None:
    """Force l'ajout du site-packages local (.venv) même si python système est lancé."""
    root = Path(__file__).parent
    win_site = root / ".venv" / "Lib" / "site-packages"
    if win_site.exists():
        sys.path.insert(0, str(win_site))


_bootstrap_site_packages()


class Api:
    """Backend API exposée au front (JS) via pywebview."""

    def __init__(self, dsn: str, instant_client_dir: Optional[Path] = None) -> None:
        self.dsn = dsn
        self.instant_client_dir = instant_client_dir
        self._init_oracle_client()
        self.window: Optional[webview.Window] = None
        self._cached_user: Optional[str] = None
        self._cached_password: Optional[str] = None

    def set_window(self, window: webview.Window) -> None:
        self.window = window

    def _init_oracle_client(self) -> None:
        """Initialise l'instant client Oracle si présent (optionnel)."""
        try:
            import oracledb
        except Exception:
            return

        if self.instant_client_dir and self.instant_client_dir.exists():
            try:
                oracledb.init_oracle_client(lib_dir=str(self.instant_client_dir))
            except Exception:
                # Si l'initialisation échoue, on laisse le mode thin prendre le relais.
                pass

    def test_connection(self, username: str, password: str) -> Dict[str, str]:
        """Teste la connexion à Oracle en retournant un message."""
        try:
            import oracledb
        except Exception as exc:
            return {"ok": "false", "message": f"Module oracledb indisponible : {exc}"}

        dsn = self.dsn
        try:
            with oracledb.connect(user=username, password=password, dsn=dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM dual")
                    cursor.fetchone()
            return {"ok": "true", "message": "Connexion réussie."}
        except Exception as exc:  # noqa: BLE001
            return {"ok": "false", "message": f"Échec de connexion : {exc}"}

    def _query_assures(self, username: str, password: str, nir_value: str):
        """Exécute la requête assurés (recherche par préfixe insensible à la casse)."""
        try:
            import oracledb
        except Exception as exc:
            return {"error": f"Module oracledb indisponible : {exc}", "rows": []}

        sql = """
            SELECT
                ind.nom_usage,
                ind.prenom_usage,
                ind.date_naissance,
                ind.sexe,
                COALESCE(mi.nir, mi.nir_provisoire_vision) AS nir,
                ind.email,
                p.libelle AS pays_nationalite,
                ind.date_deces,
                tconind.libelle AS type_contrat_individu,
                ac.numero_adherent,
                ac.raison_sociale,
                ct.date_effet AS date_effet_contrat,
                ct.date_conditions AS date_conditions_contrat
            FROM individu ind
            LEFT JOIN matricule_individu mi
                ON ind.ind_id = mi.ind_id
               AND mi.si_actif = 1
            LEFT JOIN pays p
                ON ind.pay_id_nat_principale = p.pay_id
            LEFT JOIN contrat ct
                ON ind.ind_id = ct.ind_id
               AND ct.si_actif = 1
            LEFT JOIN type_contrat_individu tconind
                ON ct.tconind_id = tconind.tconind_id
            LEFT JOIN association_cultuelle ac
                ON ct.ac_id = ac.ac_id
            WHERE UPPER(COALESCE(mi.nir, mi.nir_provisoire_vision)) LIKE UPPER(:nir_pattern)
        """

        nir_pattern = f"{nir_value}%"

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, nir_pattern=nir_pattern)
                    rows = cursor.fetchall()
            return {"rows": rows, "error": None}
        except Exception as exc:  # noqa: BLE001
            return {"rows": [], "error": str(exc)}

    def _rows_to_dicts(self, rows):
        data = []
        for row in rows:
            date_naissance = row[2].strftime("%d/%m/%Y") if row[2] else None
            date_deces = row[7].strftime("%d/%m/%Y") if row[7] else None
            data.append(
                {
                    "nom_usage": row[0],
                    "prenom_usage": row[1],
                    "date_naissance": date_naissance,
                    "sexe": "Homme" if row[3] == "1MA" else "Femme",
                    "nir": row[4],
                    "email": row[5],
                    "pays_nationalite": row[6],
                    "date_deces": date_deces,
                    "type_contrat_individu": row[8],
                    "numero_adherent": row[9],
                    "raison_sociale": row[10],
                    "date_effet_contrat": row[11].strftime("%d/%m/%Y") if row[11] else None,
                    "date_conditions_contrat": row[12].strftime("%d/%m/%Y") if row[12] else None,
                }
            )
        return data

    def fetch_assure(self, username: str, password: str, nir: str) -> Dict[str, object]:
        """Récupère les infos d'un assuré par NIR ou NIR provisoire."""
        # Cache credentials on first successful call
        if username and password:
            self._cached_user = username
            self._cached_password = password
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        result = self._query_assures(username, password, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Échec de récupération : {result['error']}", "data": []}

        data = self._rows_to_dicts(result["rows"])
        if not data:
            return {"ok": "false", "message": "Aucun assuré trouvé pour ce motif NIR.", "data": []}

        return {"ok": "true", "message": f"{len(data)} assuré(s) trouvé(s).", "data": data}

    def export_assure(self, username: str, password: str, nir: str) -> Dict[str, str]:
        """Génère un Excel avec les onglets, à partir du motif NIR."""
        # Reuse cached credentials if provided empty
        if (not username or not password) and self._cached_user and self._cached_password:
            username = self._cached_user
            password = self._cached_password

        if not username or not password:
            return {"ok": "false", "message": "Identifiants manquants pour l'export."}
        from openpyxl import Workbook

        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant pour l'export."}

        result = self._query_assures(username, password, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Échec de récupération : {result['error']}"}

        data = self._rows_to_dicts(result["rows"])
        if not data:
            return {"ok": "false", "message": "Aucun assuré trouvé pour ce motif NIR, export impossible."}

        # Prépare le nom de fichier
        first = data[0]
        fullname = f"{first.get('nom_usage','') or ''} {first.get('prenom_usage','') or ''}".strip() or "Assure"
        nir_clean = first.get("nir") or nir_value
        base_name = f"{nir_clean} - {fullname}".strip()
        safe_name = "".join(c if c not in '\\/:*?"<>|' else "_" for c in base_name) + ".xlsx"

        # Demande le chemin de sauvegarde
        if not self.window:
            return {"ok": "false", "message": "Fenêtre pywebview indisponible pour ouvrir la boîte de dialogue."}
        dialog_result = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename=safe_name)
        if not dialog_result:
            return {"ok": "false", "message": "Export annulé."}

        path = dialog_result[0]

        # Création du classeur
        wb = Workbook()
        ws_info = wb.active
        ws_info.title = "Infos personnels"
        headers = [
            "NIR",
            "Nom usage",
            "Prénom usage",
            "Date naissance",
            "Sexe",
            "Email",
            "Pays nationalité",
            "Date décès",
            "Type contrat individu",
            "Numéro adhérent",
            "Raison sociale",
            "Date effet contrat",
            "Date conditions contrat",
        ]
        ws_info.append(headers)
        for item in data:
            ws_info.append(
                [
                    item.get("nir"),
                    item.get("nom_usage"),
                    item.get("prenom_usage"),
                    item.get("date_naissance"),
                    item.get("sexe"),
                    item.get("email"),
                    item.get("pays_nationalite"),
                    item.get("date_deces"),
                    item.get("type_contrat_individu"),
                    item.get("numero_adherent"),
                    item.get("raison_sociale"),
                    item.get("date_effet_contrat"),
                    item.get("date_conditions_contrat"),
                ]
            )

        # Feuilles placeholders pour autres onglets
        for title in ["CSG", "RDS", "Assurance maladie", "Retraite"]:
            ws = wb.create_sheet(title)
            ws.append([title])
            ws.append(["Données à venir"])

        try:
            wb.save(path)
            return {"ok": "true", "message": f"Export réussi : {path}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": "false", "message": f"Échec de sauvegarde : {exc}"}


def main() -> None:
    """Launch a native window that renders the local HTML/CSS UI."""
    root = Path(__file__).parent
    html_path = root / "templates" / "index.html"
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    dsn = "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=visicaredev)(PORT=1521)))(CONNECT_DATA=(SERVICE_NAME=VISIP)))"
    instant_client_dir = Path(r"C:\Program Files\Oracle\instantclient_23_8")
    api = Api(dsn=dsn, instant_client_dir=instant_client_dir if instant_client_dir.exists() else None)

    window = webview.create_window(
        "IDENT - SIED V1.0",
        html_path.as_uri(),
        width=960,
        height=640,
        resizable=True,
        js_api=api,
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
