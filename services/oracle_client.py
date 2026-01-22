from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional


def _format_date(value):
    return value.strftime("%d/%m/%Y") if value else None


class OracleClient:
    """Client Oracle centralisé (initialisation + requêtes Assurés)."""

    def __init__(self, dsn: str, instant_client_dir: Optional[Path] = None) -> None:
        self.dsn = dsn
        self.instant_client_dir = instant_client_dir
        self._init_oracle_client()

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

    def test_connection(self, username: str, password: str) -> Optional[str]:
        """Retourne None si OK, sinon le message d'erreur."""
        try:
            import oracledb
        except Exception as exc:
            return f"Module oracledb indisponible : {exc}"

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM dual")
                    cursor.fetchone()
            return None
        except Exception as exc:  # noqa: BLE001
            return str(exc)

    def query_assures(
        self,
        username: str,
        password: str,
        nir_value: Optional[str],
        nom_value: Optional[str],
        prenom_value: Optional[str],
        order_by: str = "nir",
    ) -> Dict[str, object]:
        """Exécute la requête assurés par filtres (préfixe), insensible à la casse."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        nir_pattern = f"{nir_value}%" if nir_value else None
        nom_pattern = f"{nom_value}%" if nom_value else None
        prenom_pattern = f"{prenom_value}%" if prenom_value else None

        order_field = {
            "nir": "as_NNI",
            "nom": "as_nompat",
            "prenom": "as_prenoms",
        }.get(order_by, "as_NNI")

        sql = """
            SELECT
                as_NNI,
                as_nompat,
                as_prenoms,
                as_dtnais,
                cv.cv_lib
            FROM AT_AS#ASSURE
            LEFT JOIN AT_CV#civilite cv ON ass.ascv_id = cv.cv_id
            WHERE ( :nir_pattern IS NULL OR UPPER(as_NNI) LIKE UPPER(:nir_pattern) )
              AND ( :nom_pattern IS NULL OR UPPER(as_nompat) LIKE UPPER(:nom_pattern) )
              AND ( :prenom_pattern IS NULL OR UPPER(as_prenoms) LIKE UPPER(:prenom_pattern) )
        """

        sql = f"{sql} ORDER BY {order_field}"

        try:
            params = {
                "nir_pattern": nir_pattern,
                "nom_pattern": nom_pattern,
                "prenom_pattern": prenom_pattern,
            }
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append(
                {
                    "nir": row[0],
                    "nom_usage": row[1],
                    "prenom_usage": row[2],
                    "date_naissance": _format_date(row[3]),
                    "civilite": row[4],
                    "sexe": None,
                    "email": None,
                    "pays_nationalite": None,
                    "date_deces": None,
                    "type_contrat_individu": None,
                    "numero_adherent": None,
                    "raison_sociale": None,
                    "date_effet_contrat": None,
                    "date_conditions_contrat": None,
                }
            )
        return {"data": data, "error": None}


def build_assure_workbook(data: List[Dict[str, object]]):
    """Construit un classeur Excel pour les assurés."""
    from openpyxl import Workbook

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

    for title in ["CSG", "RDS", "Assurance maladie", "Retraite"]:
        ws = wb.create_sheet(title)
        ws.append([title])
        ws.append(["Données à venir"])

    return wb
