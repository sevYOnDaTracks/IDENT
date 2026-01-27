from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import webview

from services.oracle_client import OracleClient, build_assure_workbook, build_collectivite_workbook


def _bootstrap_site_packages() -> None:
    """Force the local .venv site-packages even if using system Python."""
    root = Path(__file__).parent
    win_site = root / ".venv" / "Lib" / "site-packages"
    if win_site.exists():
        sys.path.insert(0, str(win_site))


_bootstrap_site_packages()


class Api:
    """Backend API exposed to the frontend (pywebview)."""

    def __init__(self, client: OracleClient) -> None:
        self.client = client
        self.window: Optional[webview.Window] = None
        self._cached_user: Optional[str] = None
        self._cached_password: Optional[str] = None
        self._selected_collectivite: Optional[dict] = None
        self._selected_assure_nni: Optional[str] = None

    def set_window(self, window: webview.Window) -> None:
        self.window = window

    def _resolve_credentials(self, username: Optional[str], password: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
        user = username or self._cached_user
        pwd = password or self._cached_password
        if user and pwd:
            self._cached_user = user
            self._cached_password = pwd
            return user, pwd
        return None, None

    def test_connection(self, username: str, password: str):
        error = self.client.test_connection(username, password)
        if error:
            return {"ok": "false", "message": f"Echec de connexion : {error}"}
        self._cached_user = username
        self._cached_password = password
        return {"ok": "true", "message": "Connexion reussie."}

    def reset_credentials(self):
        """Réinitialise le cache d'identifiants côté backend."""
        self._cached_user = None
        self._cached_password = None
        return {"ok": "true"}

    def set_selected_collectivite(self, payload: dict):
        self._selected_collectivite = payload or None
        return {"ok": "true"}

    def get_selected_collectivite(self):
        return {"ok": "true", "data": self._selected_collectivite}

    def set_selected_assure_nni(self, nni: str):
        self._selected_assure_nni = (nni or "").strip() or None
        return {"ok": "true"}

    def get_selected_assure_nni(self):
        return {"ok": "true", "data": self._selected_assure_nni}

    def fetch_assure(self, username: str, password: str, nir: str, nom: str = "", prenom: str = "", tri: str = "nir"):
        nir_value = (nir or "").strip()
        nom_value = (nom or "").strip()
        prenom_value = (prenom or "").strip()

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assures(user, pwd, nir_value, nom_value, prenom_value, order_by=tri or "nir")
        if result["error"]:
            return {"ok": "false", "message": f"Echec de récuperation : {result['error']}", "data": []}

        data = result["data"]
        if not data:
            return {"ok": "false", "message": "Aucun assure trouve pour ce motif NIR.", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} assure(s) trouve(s).", "data": data}

    def fetch_collectivites(self, username: str, password: str, numero: str, denom1: str, code_postal: str):
        numero_value = (numero or "").strip()
        denom1_value = (denom1 or "").strip()
        cp_value = (code_postal or "").strip()

        if not (numero_value or denom1_value or cp_value):
            return {"ok": "false", "message": "Renseignez au moins un filtre (numéro, dénomination 1 ou le code postal).", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_collectivites(user, pwd, numero_value, denom1_value, cp_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"]
        if not data:
            return {"ok": "false", "message": "Aucune collectivité trouvée.", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} collectivité(s) trouvée(s).", "data": data}

    def fetch_collectivite_adresse(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivité manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_collectivite_adresse(user, pwd, collect_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}
        if not result["data"]:
            return {"ok": "false", "message": "Collectivité introuvable.", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Détails collectivité récupérés.", "data": result["data"]}

    def fetch_collectivite_identification(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_collectivite_identification(user, pwd, collect_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}
        if not result["data"]:
            return {"ok": "false", "message": "Collectivite introuvable.", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Identification collectivite recuperee.", "data": result["data"]}

    def fetch_collectivite_situations(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_collectivite_situations(user, pwd, collect_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Situations collectivité récupérées.", "data": result["data"]}

    def fetch_collectivite_fusions(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_collectivite_fusions(user, pwd, collect_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Fusions collectivité récupérées.", "data": result["data"]}

    def fetch_collectivite_responsable_maladie(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_collectivite_responsable(user, pwd, collect_value, 1)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Responsable maladie récupéré.", "data": result["data"]}

    def fetch_collectivite_responsable_vieillesse(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_collectivite_responsable(user, pwd, collect_value, 2)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Responsable vieillesse récupéré.", "data": result["data"]}

    def fetch_collectivite_assures(self, username: str, password: str, collect_id: str, filter_type: str = "tout", tri: str = "nom"):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        filter_value = (filter_type or "tout").strip().lower()
        tri_value = (tri or "nom").strip().lower()
        result = self.client.query_collectivite_assures(user, pwd, collect_value, filter_value, tri_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Assurés collectivité récupérés.", "data": result["data"]}

    def fetch_collectivite_communautes(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_collectivite_communautes(user, pwd, collect_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Communautés collectivité récupérées.", "data": result["data"]}

    def fetch_collectivite_referent_maladie(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_collectivite_referent_maladie(user, pwd, collect_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Référent collectivité récupéré.", "data": result["data"]}

    def export_assure(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant pour l'export."}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants pour l'export."}

        result = self.client.query_assures(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}"}

        data = result["data"]
        if not data:
            return {"ok": "false", "message": "Aucun assure trouve pour ce motif NIR, export impossible."}

        first = data[0]
        fullname = f"{first.get('nom_usage','') or ''} {first.get('prenom_usage','') or ''}".strip() or "Assure"
        nir_clean = first.get("nir") or nir_value
        base_name = f"{nir_clean} - {fullname}".strip()
        safe_name = "".join(c if c not in '\\/:*?"<>|' else "_" for c in base_name) + ".xlsx"

        if not self.window:
            return {"ok": "false", "message": "Fenetre pywebview indisponible pour ouvrir la boite de dialogue."}
        dialog_result = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename=safe_name)
        if not dialog_result:
            return {"ok": "false", "message": "Export annule."}

        path = dialog_result[0] if isinstance(dialog_result, (list, tuple)) else dialog_result
        path = str(path)
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"
        wb = build_assure_workbook(data)
        try:
            wb.save(path)
            if not Path(path).exists():
                return {"ok": "false", "message": "Export termine mais fichier introuvable."}
            return {"ok": "true", "message": f"Export reussi : {path}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": "false", "message": f"Echec de sauvegarde : {exc}"}

    def export_collectivite(self, username: str, password: str, collect_id: str):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivité manquant pour l'export."}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants pour l'export."}

        ident_result = self.client.query_collectivite_identification(user, pwd, collect_value)
        if ident_result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {ident_result['error']}"}
        identification = ident_result["data"] or {}

        def safe_data(result, empty):
            if result.get("error"):
                return empty
            return result.get("data") or empty

        adresse = safe_data(self.client.query_collectivite_adresse(user, pwd, collect_value), {})
        resp_mal = safe_data(self.client.query_collectivite_responsable(user, pwd, collect_value, 1), {})
        resp_vie = safe_data(self.client.query_collectivite_responsable(user, pwd, collect_value, 2), {})
        assures = safe_data(self.client.query_collectivite_assures(user, pwd, collect_value, "tout", "nom"), [])
        communautes = safe_data(self.client.query_collectivite_communautes(user, pwd, collect_value), [])
        referent = safe_data(self.client.query_collectivite_referent_maladie(user, pwd, collect_value), {})
        situations = safe_data(self.client.query_collectivite_situations(user, pwd, collect_value), [])
        fusions = safe_data(self.client.query_collectivite_fusions(user, pwd, collect_value), [])

        denom1 = identification.get("denom1") or "Collectivite"
        base_name = f"{collect_value} - {denom1}".strip()
        safe_name = "".join(c if c not in '\\/:*?"<>|' else "_" for c in base_name) + ".xlsx"

        if not self.window:
            return {"ok": "false", "message": "Fenêtre pywebview indisponible pour ouvrir la boîte de dialogue."}
        dialog_result = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename=safe_name)
        if not dialog_result:
            return {"ok": "false", "message": "Export annulé."}

        path = dialog_result[0] if isinstance(dialog_result, (list, tuple)) else dialog_result
        path = str(path)
        if not path.lower().endswith(".xlsx"):
            path = f"{path}.xlsx"
        wb = build_collectivite_workbook(
            collect_value,
            identification,
            adresse,
            resp_mal,
            resp_vie,
            assures,
            communautes,
            referent,
            situations,
            fusions,
        )
        try:
            wb.save(path)
            if not Path(path).exists():
                return {"ok": "false", "message": "Export termine mais fichier introuvable."}
            return {"ok": "true", "message": f"Export reussi : {path}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": "false", "message": f"Echec de sauvegarde : {exc}"}


def main() -> None:
    """Launch a native window that renders the local HTML/CSS UI."""
    root = Path(__file__).parent
    html_path = root / "templates" / "home.html"
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    dsn = "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=CAVIMAC-ETUD2)(PORT=1521)))(CONNECT_DATA=(SERVICE_NAME=ETUDN)))"
    instant_client_dir = Path(r"C:\Program Files\Oracle\instantclient_23_8")
    client = OracleClient(dsn=dsn, instant_client_dir=instant_client_dir if instant_client_dir.exists() else None)
    api = Api(client=client)

    window = webview.create_window(
        "IDENT - SIED V1.0",
        html_path.as_uri(),
        width=1280,
        height=720,
        resizable=True,
        js_api=api,
    )
    api.set_window(window)
    webview.start()


if __name__ == "__main__":
    main()
