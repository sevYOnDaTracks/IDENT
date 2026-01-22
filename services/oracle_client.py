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

    def query_assures(self, username: str, password: str, nir_value: str) -> Dict[str, object]:
        """Exécute la requête assurés par préfixe de NIR (insensible à la casse)."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        nir_pattern = f"{nir_value}%"
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

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, nir_pattern=nir_pattern)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append(
                {
                    "nom_usage": row[0],
                    "prenom_usage": row[1],
                    "date_naissance": _format_date(row[2]),
                    "sexe": "Homme" if row[3] == "1MA" else "Femme",
                    "nir": row[4],
                    "email": row[5],
                    "pays_nationalite": row[6],
                    "date_deces": _format_date(row[7]),
                    "type_contrat_individu": row[8],
                    "numero_adherent": row[9],
                    "raison_sociale": row[10],
                    "date_effet_contrat": _format_date(row[11]),
                    "date_conditions_contrat": _format_date(row[12]),
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
