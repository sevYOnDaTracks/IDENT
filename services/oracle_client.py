from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple


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

    def query_user_login(self, username: str, password: str, email: str, user_password: str) -> Dict[str, object]:
        """Vérifie un utilisateur applicatif par email + mot de passe."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": None, "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                usr.user_id,
                usr.prenom,
                usr.nom,
                usr.email,
                usr.mot_de_passe,
                usr.service
            FROM USER_IDENT usr
            WHERE TRIM(LOWER(usr.email)) = TRIM(LOWER(:identifier))
        """
        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"identifier": email})
                    row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            return {"data": None, "error": str(exc)}

        if not row:
            return {"data": None, "error": None}

        stored_pwd = (row[4] or "").strip()
        provided_pwd = (user_password or "").strip()
        if stored_pwd != provided_pwd:
            return {"data": None, "error": None}

        data = {
            "user_id": row[0],
            "prenoms": row[1],
            "nom": row[2],
            "email": row[3],
            "service": row[5],
        }
        return {"data": data, "error": None}

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
            "nir": "ass.as_NNI",
            "nom": "ass.as_nompat",
            "prenom": "ass.as_prenoms",
        }.get(order_by, "ass.as_NNI")

        sql = """
            SELECT
                ass.as_NNI,
                ass.as_nompat,
                ass.as_prenoms,
                ass.as_dtnais,
                cv.cv_lib
            FROM AT_AS#ASSURE ass
            LEFT JOIN AT_CV#civilite cv ON ass.ascv_id = cv.cv_id
            WHERE ( :nir_pattern IS NULL OR UPPER(ass.as_NNI) LIKE UPPER(:nir_pattern) )
              AND ( :nom_pattern IS NULL OR UPPER(ass.as_nompat) LIKE UPPER(:nom_pattern) )
              AND ( :prenom_pattern IS NULL OR UPPER(ass.as_prenoms) LIKE UPPER(:prenom_pattern) )
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

    def query_collectivites(
        self,
        username: str,
        password: str,
        numero: str,
        denom1: str,
        code_postal: str,
    ) -> Dict[str, object]:
        """Recherche des collectivites par numero / denom1 / code postal (prefixes, insensible à la casse)."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        params = {
            "num_pattern": f"{numero}%" if numero else None,
            "denom_pattern": f"{denom1}%" if denom1 else None,
            "cp_pattern": f"{code_postal}%" if code_postal else None,
        }

        sql = """
            SELECT
                cl.cl_id,
                cl.cl_denom1,
                cl.cl_adrcp,
                cl.cl_adrvil
            FROM AT_CL#COLLECTIVITE cl
            WHERE (:num_pattern IS NULL OR UPPER(cl.cl_id) LIKE UPPER(:num_pattern))
              AND (
                :denom_pattern IS NULL
                OR UPPER(cl.cl_denom1) LIKE UPPER(:denom_pattern)
                OR UPPER(cl.cl_adrvil) LIKE UPPER(:denom_pattern)
              )
              AND (:cp_pattern IS NULL OR UPPER(cl.cl_adrcp) LIKE UPPER(:cp_pattern))
            ORDER BY cl.cl_id
        """

        try:
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
                    "numero": row[0],
                    "denom1": row[1],
                    "denom2": None,
                    "cp": row[2],
                    "ville": row[3],
                }
            )
        return {"data": data, "error": None}

    def query_collectivite_adresse(
        self,
        username: str,
        password: str,
        collect_id: str,
    ) -> Dict[str, object]:
        """Récupère les informations d'adresse d'une collectivité par identifiant."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": None, "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": None, "error": "Identifiant collectivité manquant."}

        sql = """
            SELECT
                cl.cl_id,
                cl.cl_denom1,
                cl.cl_denom2,
                cl.cl_adrcp,
                cl.cl_adr1,
                cl.cl_adr2,
                cl.cl_adr3,
                cl.cl_adr4,
                cl.cl_adrvil,
                p.py_lib,
                cl.cl_email,
                cl.cl_tel1,
                cl.cl_tec1,
                cl.cl_npai,
                cl.cl_dtadr
            FROM AT_CL#COLLECTIVITE cl
            LEFT JOIN at_py#pays p on cl.clpy_id = p.py_id
            WHERE cl.cl_id = :collect_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            return {"data": None, "error": str(exc)}

        if not row:
            return {"data": None, "error": None}

        data = {
            "numero": row[0],
            "denom1": row[1],
            "denom2": row[2],
            "cp": row[3],
            "adr1": row[4],
            "adr2": row[5],
            "adr3": row[6],
            "adr4": row[7],
            "ville": row[8],
            "pays": row[9],
            "email": row[10],
            "tel": row[11],
            "fax": row[12],
            "npai": row[13],
            "date_maj": _format_date(row[14]) if hasattr(row[14], "strftime") else row[14],
        }
        return {"data": data, "error": None}

    def query_collectivite_identification(
        self,
        username: str,
        password: str,
        collect_id: str,
    ) -> Dict[str, object]:
        """Recupere les informations d'identification d'une collectivite par identifiant."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": None, "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": None, "error": "Identifiant collectivite manquant."}

        sql = """
            SELECT
                cl.cl_id,
                cl.cl_denom1,
                cl.cl_denom2,
                cu.cu_lib,
                cl.cl_dtdec,
                cl.cl_dtcrjo,
                mv.vm_lib,
                cl.cl_dtrec,
                cl.cl_dtmaj,
                cl.cl_nblet
            FROM AT_CL#COLLECTIVITE cl
            LEFT JOIN AT_CU#Culte cu on cl.clcu_id = cu.cu_id
            LEFT JOIN at_vm#mode_vie mv on cl.clvm_id = mv.vm_id
            WHERE cl.cl_id = :collect_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            return {"data": None, "error": str(exc)}

        if not row:
            return {"data": None, "error": None}

        data = {
            "numero": row[0],
            "denom1": row[1],
            "denom2": row[2],
            "culte": row[3],
            "date_adhesion": _format_date(row[4]) if hasattr(row[4], "strftime") else row[4],
            "date_journal": _format_date(row[5]) if hasattr(row[5], "strftime") else row[5],
            "mode_vie": row[6],
            "recult": _format_date(row[7]) if hasattr(row[7], "strftime") else row[7],
            "date_maj": _format_date(row[8]) if hasattr(row[8], "strftime") else row[8],
            "nb_lettres": row[9],
        }
        return {"data": data, "error": None}

    def query_collectivite_situations(
        self,
        username: str,
        password: str,
        collect_id: str,
    ) -> Dict[str, object]:
        """Recupere l'historique des situations pour une collectivite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": [], "error": "Identifiant collectivite manquant."}

        sql = """
            SELECT
                his.hc_dtdeb,
                cs.cs_lib,
                CASE
                    WHEN his.hccs_id = 'U' THEN fc.fccl2_id
                    ELSE ''
                END AS coll_accueil,
                his.hc_dtmaj
            FROM at_hc#his_sit_col his
            LEFT JOIN at_cs#lib_sit_col cs on his.hccs_id = cs.cs_id
            LEFT JOIN at_fc#fusion_col fc on his.HCCL_ID = fc.fccl1_id
            WHERE his.HCCL_ID = :collect_id
            ORDER BY his.hc_dtmaj desc
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append(
                {
                    "date_effet": _format_date(row[0]) if hasattr(row[0], "strftime") else row[0],
                    "libelle": row[1],
                    "coll_accueil": row[2],
                    "date_maj": _format_date(row[3]) if hasattr(row[3], "strftime") else row[3],
                }
            )
        return {"data": data, "error": None}

    def query_collectivite_fusions(
        self,
        username: str,
        password: str,
        collect_id: str,
    ) -> Dict[str, object]:
        """Recupere l'historique des collectivites reprises suite a fusion."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": [], "error": "Identifiant collectivite manquant."}

        sql = """
            SELECT
                a.fc_dteff,
                a.fccl1_id,
                a.fc_dtmaj
            FROM at_fc#fusion_col a
            WHERE a.fccl2_id = :collect_id
            ORDER BY a.fc_dtmaj desc
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append(
                {
                    "date_effet": _format_date(row[0]) if hasattr(row[0], "strftime") else row[0],
                    "coll_transf": row[1],
                    "date_maj": _format_date(row[2]) if hasattr(row[2], "strftime") else row[2],
                }
            )
        return {"data": data, "error": None}

    def query_collectivite_responsable(
        self,
        username: str,
        password: str,
        collect_id: str,
        role_id: int,
    ) -> Dict[str, object]:
        """Recupere les informations d'un responsable (maladie/vieillesse) pour une collectivite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": None, "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": None, "error": "Identifiant collectivite manquant."}

        sql = """
            SELECT
                responsable.rs_nomrespo,
                responsable.rs_adr1,
                responsable.rs_adr2,
                responsable.rs_adr3,
                responsable.rs_adr4,
                responsable.rs_adrcp,
                responsable.rs_adrvil,
                p_adresse.py_lib,
                responsable.rs_email,
                responsable.rs_tel1,
                responsable.rs_tec1,
                responsable.rs_dtmaj
            FROM AT_CL#COLLECTIVITE a
            LEFT JOIN AT_RS#RESPONSABLE responsable
                ON a.cl_id = responsable.rscl_id
                AND responsable.rsst_id = :role_id
            LEFT JOIN at_py#pays p_adresse
                ON responsable.rspy_id = p_adresse.py_id
            WHERE a.cl_id = :collect_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id, "role_id": role_id})
                    row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            return {"data": None, "error": str(exc)}

        if not row:
            return {"data": None, "error": None}

        data = {
            "nom": row[0],
            "adr1": row[1],
            "adr2": row[2],
            "adr3": row[3],
            "adr4": row[4],
            "cp": row[5],
            "ville": row[6],
            "pays": row[7],
            "email": row[8],
            "tel": row[9],
            "fax": row[10],
            "date_maj": _format_date(row[11]) if hasattr(row[11], "strftime") else row[11],
        }
        return {"data": data, "error": None}

    def query_collectivite_assures(
        self,
        username: str,
        password: str,
        collect_id: str,
        filter_type: str,
        order_by: str,
    ) -> Dict[str, object]:
        """Recupere la liste des assures d'une collectivite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": [], "error": "Identifiant collectivite manquant."}

        filter_clause = ""
        if filter_type == "maladie":
            filter_clause = """
              AND sm.smsa_id IS NOT NULL
              AND (sm.sm_dteffin = TO_DATE('31-12-3999', 'DD-MM-YYYY') OR sm.sm_dteffin IS NULL)
            """
        elif filter_type == "vieillesse":
            filter_clause = """
              AND sv.svsa_id IS NOT NULL
              AND (sv.sv_dteffin = TO_DATE('31-12-3999', 'DD-MM-YYYY') OR sv.sv_dteffin IS NULL)
            """
        elif filter_type == "adresse":
            filter_clause = " AND b.as_typadr = 2"

        order_field = "b.as_nompat" if order_by != "nni" else "b.as_nni"

        sql = f"""
            WITH
            sm_last AS (
              SELECT *
              FROM (
                SELECT
                  c.*,
                  ROW_NUMBER() OVER (
                    PARTITION BY c.smas_id
                    ORDER BY
                      CASE WHEN c.sm_dteffin IS NULL THEN 1 ELSE 0 END DESC,
                      c.sm_dteffin DESC,
                      c.sm_dtefdeb DESC
                  ) rn
                FROM AT_SM#ASS_SIT_CAM c
              )
              WHERE rn = 1
            ),
            sv_last AS (
              SELECT *
              FROM (
                SELECT
                  d.*,
                  ROW_NUMBER() OVER (
                    PARTITION BY d.svas_id
                    ORDER BY
                      CASE WHEN d.sv_dteffin IS NULL THEN 1 ELSE 0 END DESC,
                      d.sv_dteffin DESC,
                      d.sv_dtefdeb DESC
                  ) rn
                FROM AT_SV#ASS_SIT_VIC d
              )
              WHERE rn = 1
            )
            SELECT DISTINCT
              b.as_nompat,
              b.as_prenoms,
              b.as_nni,
              sm.smsa_id,
              sm.sm_dtefdeb,
              sm.sm_dteffin,
              a.accl_id,
              sv.svsa_id,
              sv.sv_dtefdeb,
              sv.sv_dteffin,
              a.accl_id,
              CASE
                WHEN b.as_typadr = 1 THEN 'Assuré'
                ELSE 'Collectivité'
              END AS type_adresse
            FROM AT_AC#ASS_COL a
            LEFT JOIN AT_AS#ASSURE b
              ON a.acas_id = b.as_id
            LEFT JOIN sm_last sm
              ON b.as_id = sm.smas_id
            LEFT JOIN sv_last sv
              ON b.as_id = sv.svas_id
            WHERE a.accl_id = :collect_id
              AND a.ac_dteffin = TO_DATE('31-12-3999', 'DD-MM-YYYY')
              {filter_clause}
            ORDER BY {order_field}
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append(
                {
                    "nom": row[0],
                    "prenoms": row[1],
                    "nni": row[2],
                    "code_maladie": row[3],
                    "date_effet_maladie": _format_date(row[4]) if hasattr(row[4], "strftime") else row[4],
                    "date_fin_maladie": _format_date(row[5]) if hasattr(row[5], "strftime") else row[5],
                    "num_coll_maladie": row[6],
                    "code_vieillesse": row[7],
                    "date_effet_vieillesse": _format_date(row[8]) if hasattr(row[8], "strftime") else row[8],
                    "date_fin_vieillesse": _format_date(row[9]) if hasattr(row[9], "strftime") else row[9],
                    "num_coll_vieillesse": row[10],
                    "type_adresse": row[11],
                }
            )
        return {"data": data, "error": None}

    def query_collectivite_communautes(
        self,
        username: str,
        password: str,
        collect_id: str,
    ) -> Dict[str, object]:
        """Recupere la liste des communautes pour une collectivite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": [], "error": "Identifiant collectivite manquant."}

        sql = """
            SELECT
                cl.cl_id,
                ROW_NUMBER() OVER (ORDER BY co.co_denom1) AS rang,
                co.co_denom1,
                co.co_denom2,
                co.co_adrcp,
                co.co_adrvil
            FROM AT_CO#COMMUNAUTE co
            LEFT JOIN at_cl#collectivite cl
                ON cl.cl_id = co.cocl_id
            WHERE cl.cl_id = :collect_id
            ORDER BY co.co_denom1
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append(
                {
                    "numero": row[0],
                    "rang": row[1],
                    "denom1": row[2],
                    "denom2": row[3],
                    "cp": row[4],
                    "ville": row[5],
                }
            )
        return {"data": data, "error": None}

    def query_collectivite_referent_maladie(
        self,
        username: str,
        password: str,
        collect_id: str,
    ) -> Dict[str, object]:
        """Recupere le referent maladie pour une collectivite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": None, "error": f"Module oracledb indisponible : {exc}"}

        if not collect_id:
            return {"data": None, "error": "Identifiant collectivite manquant."}

        sql = """
            SELECT
                resp.rmc_nom,
                resp.rmc_prenom,
                resp.rmc_numvoie,
                resp.rmc_libvoie,
                resp.rmc_comad,
                resp.rmc_codpos,
                resp.rmc_burdis,
                p.py_lib,
                resp.rmc_email,
                resp.rmc_tel1,
                resp.rmc_tec1,
                resp.rmc_dtmaj
            FROM AT_RMC#REF_MAL_COLL resp
            LEFT JOIN at_cl#collectivite cl on resp.rmccl_id = cl.cl_id
            LEFT JOIN at_py#pays p on resp.rmcpy_id = p.py_id
            WHERE cl.cl_id = :collect_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, {"collect_id": collect_id})
                    row = cursor.fetchone()
        except Exception as exc:  # noqa: BLE001
            return {"data": None, "error": str(exc)}

        if not row:
            return {"data": None, "error": None}

        data = {
            "nom": row[0],
            "prenom": row[1],
            "num_voie": row[2],
            "lib_voie": row[3],
            "complement": row[4],
            "cp": row[5],
            "burdis": row[6],
            "pays": row[7],
            "email": row[8],
            "tel": row[9],
            "fax": row[10],
            "date_maj": _format_date(row[11]) if hasattr(row[11], "strftime") else row[11],
        }
        return {"data": data, "error": None}

    def query_referentiel_civilites(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des civilites."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                cv.cv_id,
                cv.cv_lib
            FROM AT_CV#CIVILITE cv
            ORDER BY cv.cv_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_cultes(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des cultes."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                cu.cu_id,
                cu.cu_lib
            FROM AT_CU#CULTE cu
            ORDER BY cu.cu_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_complements_num_voie(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des complements numero de voie."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                cc.cc_id,
                cc.cc_lib
            FROM AT_CC#COM_NUM_VOI cc
            ORDER BY cc.cc_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_jod(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des justificatifs d'ouverture des droits (J.O.D)."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                jo.jo_id,
                jo.jo_lib
            FROM AT_JO#COD_JOD jo
            ORDER BY jo.jo_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_mode_vie(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des modes de vie."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                vm.vm_id,
                vm.vm_lib
            FROM AT_VM#MODE_VIE vm
            ORDER BY vm.vm_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_nature_situation(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des natures de situation."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                ns.ns_id,
                ns.ns_lib
            FROM AT_NS#LIB_NAT_SIT ns
            ORDER BY ns.ns_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_pays(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des pays."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                py.py_id,
                py.py_lib
            FROM AT_PY#PAYS py
            ORDER BY py.py_lib
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_situations(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des situations assure."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                st.st_lib,
                sa.sa_id,
                sa.sa_lib
            FROM AT_SA#LIB_SIT_ASS sa
            LEFT JOIN at_st#societe st ON sa.sast_id = st.st_id
            ORDER BY st.st_id ASC
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"categorie": row[0], "code": row[1], "libelle": row[2]})
        return {"data": data, "error": None}

    def query_referentiel_situations_collectivite(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des situations collectivite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                cs.cs_id,
                cs.cs_lib
            FROM AT_CS#LIB_SIT_COL cs
            ORDER BY cs.cs_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_type_nationalite(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des types de nationalite."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                tn.tn_id,
                tn.tn_lib
            FROM AT_TN#TYPE_NATIONAL tn
            ORDER BY tn.tn_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_type_voie(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des types de voie."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                cn.cn_id,
                cn.cn_lib
            FROM AT_CN#TYP_VOIE cn
            ORDER BY cn.cn_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
        return {"data": data, "error": None}

    def query_referentiel_societe(self, username: str, password: str) -> Dict[str, object]:
        """Retourne la liste des societes."""
        try:
            import oracledb
        except Exception as exc:
            return {"data": [], "error": f"Module oracledb indisponible : {exc}"}

        sql = """
            SELECT
                st.st_id,
                st.st_lib
            FROM AT_ST#SOCIETE st
            ORDER BY st.st_id
        """

        try:
            with oracledb.connect(user=username, password=password, dsn=self.dsn) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                    rows = cursor.fetchall()
        except Exception as exc:  # noqa: BLE001
            return {"data": [], "error": str(exc)}

        data: List[Dict[str, object]] = []
        for row in rows:
            data.append({"code": row[0], "libelle": row[1]})
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


def build_collectivite_workbook(
    collect_id: str,
    identification: Optional[Dict[str, object]],
    adresse: Optional[Dict[str, object]],
    responsable_maladie: Optional[Dict[str, object]],
    responsable_vieillesse: Optional[Dict[str, object]],
    assures: List[Dict[str, object]],
    communautes: List[Dict[str, object]],
    referent: Optional[Dict[str, object]],
    situations: List[Dict[str, object]],
    fusions: List[Dict[str, object]],
):
    """Construit un classeur Excel pour une collectivité."""
    from openpyxl import Workbook

    def _safe(value: object) -> str:
        if value is None or value == "":
            return "-"
        return str(value)

    def _append_section(ws, title: str, rows: List[Tuple[str, object]]) -> None:
        ws.append([title])
        ws.append(["Champ", "Valeur"])
        for label, val in rows:
            ws.append([label, _safe(val)])
        ws.append([])

    wb = Workbook()

    ws_ident = wb.active
    ws_ident.title = "Identification"
    _append_section(
        ws_ident,
        "Identification",
        [
            ("Numéro", collect_id),
            ("Dénomination 1", (identification or {}).get("denom1")),
            ("Dénomination 2", (identification or {}).get("denom2")),
            ("Culte", (identification or {}).get("culte")),
            ("Mode de vie", (identification or {}).get("mode_vie")),
            ("1ère adhésion", (identification or {}).get("date_adhesion")),
            ("Création journal officiel", (identification or {}).get("date_journal")),
            ("Reconnaissance cultuelle", (identification or {}).get("recult")),
            ("Date MAJ", (identification or {}).get("date_maj")),
            ("Nb lettres d'informations", (identification or {}).get("nb_lettres")),
        ],
    )

    ws_ident.append(["Historique des situations"])
    ws_ident.append(["Date effet", "Libellé situation", "N° coll. accueil", "Date MAJ"])
    for item in situations or []:
        ws_ident.append(
            [
                _safe(item.get("date_effet")),
                _safe(item.get("libelle")),
                _safe(item.get("coll_accueil")),
                _safe(item.get("date_maj")),
            ]
        )
    ws_ident.append([])
    ws_ident.append(["Collectivités reprises suite à fusion"])
    ws_ident.append(["Date effet", "N° coll. transférée", "Date MAJ"])
    for item in fusions or []:
        ws_ident.append(
            [
                _safe(item.get("date_effet")),
                _safe(item.get("coll_transf")),
                _safe(item.get("date_maj")),
            ]
        )

    ws_addr = wb.create_sheet("Adresse")
    _append_section(
        ws_addr,
        "Adresse",
        [
            ("Ligne 1", (adresse or {}).get("adr1")),
            ("Ligne 2", (adresse or {}).get("adr2")),
            ("Ligne 3", (adresse or {}).get("adr3")),
            ("Ligne 4", (adresse or {}).get("adr4")),
            ("Code postal", (adresse or {}).get("cp")),
            ("Ville", (adresse or {}).get("ville")),
            ("Pays", (adresse or {}).get("pays")),
        ],
    )
    _append_section(
        ws_addr,
        "Coordonnées",
        [
            ("Email", (adresse or {}).get("email")),
            ("Téléphone", (adresse or {}).get("tel")),
            ("Télécopie", (adresse or {}).get("fax")),
            ("NPAI", (adresse or {}).get("npai")),
            ("Date MAJ adresse", (adresse or {}).get("date_maj")),
        ],
    )

    ws_resp = wb.create_sheet("Responsables")
    _append_section(
        ws_resp,
        "Responsable maladie",
        [
            ("Nom du responsable", (responsable_maladie or {}).get("nom")),
            ("Ligne 1", (responsable_maladie or {}).get("adr1")),
            ("Ligne 2", (responsable_maladie or {}).get("adr2")),
            ("Ligne 3", (responsable_maladie or {}).get("adr3")),
            ("Ligne 4", (responsable_maladie or {}).get("adr4")),
            ("Code postal", (responsable_maladie or {}).get("cp")),
            ("Ville", (responsable_maladie or {}).get("ville")),
            ("Pays", (responsable_maladie or {}).get("pays")),
            ("Email", (responsable_maladie or {}).get("email")),
            ("Téléphone", (responsable_maladie or {}).get("tel")),
            ("Télécopie", (responsable_maladie or {}).get("fax")),
            ("Date MAJ", (responsable_maladie or {}).get("date_maj")),
        ],
    )
    _append_section(
        ws_resp,
        "Responsable vieillesse",
        [
            ("Nom du responsable", (responsable_vieillesse or {}).get("nom")),
            ("Ligne 1", (responsable_vieillesse or {}).get("adr1")),
            ("Ligne 2", (responsable_vieillesse or {}).get("adr2")),
            ("Ligne 3", (responsable_vieillesse or {}).get("adr3")),
            ("Ligne 4", (responsable_vieillesse or {}).get("adr4")),
            ("Code postal", (responsable_vieillesse or {}).get("cp")),
            ("Ville", (responsable_vieillesse or {}).get("ville")),
            ("Pays", (responsable_vieillesse or {}).get("pays")),
            ("Email", (responsable_vieillesse or {}).get("email")),
            ("Téléphone", (responsable_vieillesse or {}).get("tel")),
            ("Télécopie", (responsable_vieillesse or {}).get("fax")),
            ("Date MAJ", (responsable_vieillesse or {}).get("date_maj")),
        ],
    )

    ws_assures = wb.create_sheet("Assures")
    ws_assures.append(
        [
            "Nom",
            "Prénoms",
            "NNI",
            "Code sit. mal.",
            "Date effet sit. mal.",
            "Date fin sit. mal.",
            "Num. coll maladie en cours",
            "Code sit. vieil.",
            "Date effet sit. vieil.",
            "Date fin sit. vieil.",
            "Num. coll vieillesse en cours",
            "Type adresse",
        ]
    )
    for item in assures or []:
        ws_assures.append(
            [
                _safe(item.get("nom")),
                _safe(item.get("prenoms")),
                _safe(item.get("nni")),
                _safe(item.get("code_maladie")),
                _safe(item.get("date_effet_maladie")),
                _safe(item.get("date_fin_maladie")),
                _safe(item.get("num_coll_maladie")),
                _safe(item.get("code_vieillesse")),
                _safe(item.get("date_effet_vieillesse")),
                _safe(item.get("date_fin_vieillesse")),
                _safe(item.get("num_coll_vieillesse")),
                _safe(item.get("type_adresse")),
            ]
        )

    ws_commu = wb.create_sheet("Communautes")
    ws_commu.append(["N° Collectivité", "Rang", "Dénomination 1", "Dénomination 2", "Code postal", "Ville"])
    for item in communautes or []:
        ws_commu.append(
            [
                _safe(item.get("numero")),
                _safe(item.get("rang")),
                _safe(item.get("denom1")),
                _safe(item.get("denom2")),
                _safe(item.get("cp")),
                _safe(item.get("ville")),
            ]
        )

    ws_ref = wb.create_sheet("Referent")
    _append_section(
        ws_ref,
        "Référent maladie",
        [
            ("Nom", (referent or {}).get("nom")),
            ("Prénom", (referent or {}).get("prenom")),
            ("Numéro de voie", (referent or {}).get("num_voie")),
            ("Libellé de voie", (referent or {}).get("lib_voie")),
            ("Complément adresse", (referent or {}).get("complement")),
            ("Code postal", (referent or {}).get("cp")),
            ("Bureau distributeur", (referent or {}).get("burdis")),
            ("Pays", (referent or {}).get("pays")),
        ],
    )
    _append_section(
        ws_ref,
        "Coordonnées",
        [
            ("Email", (referent or {}).get("email")),
            ("Téléphone", (referent or {}).get("tel")),
            ("Télécopie", (referent or {}).get("fax")),
            ("Date MAJ", (referent or {}).get("date_maj")),
        ],
    )

    return wb
