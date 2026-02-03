from __future__ import annotations

import sys
import traceback
import os
from pathlib import Path
from typing import Optional, Tuple

import webview

from services.oracle_client import OracleClient, build_assure_workbook, build_collectivite_workbook

ORACLE_APP_USER = "ASCOT"
ORACLE_APP_PASSWORD = "ASCOT"


def _bootstrap_site_packages() -> None:
    """Force the local .venv site-packages even if using system Python."""
    root = Path(__file__).parent
    win_site = root / ".venv" / "Lib" / "site-packages"
    if win_site.exists():
        sys.path.insert(0, str(win_site))


_bootstrap_site_packages()


def _hide_console_window() -> None:
    """Hide the console window for PyInstaller console builds on Windows."""
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        return


def _resource_base_dir() -> Path:
    """Return base directory for bundled resources."""
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            if (base / "templates").exists():
                return base
        if (exe_dir / "templates").exists():
            return exe_dir
        if meipass:
            return Path(meipass)
        return exe_dir
    return Path(__file__).parent


def _resource_path(*parts: str) -> Path:
    return _resource_base_dir().joinpath(*parts)


def _find_instant_client_dir() -> Optional[Path]:
    """
    Try to locate Oracle Instant Client for python-oracledb thick mode.

    Why: some Oracle server versions are not supported in thin mode (DPY-3010),
    so we need thick mode on machines that don't have a local Oracle client installed.
    """
    env = (os.environ.get("IDENT_INSTANTCLIENT_DIR") or os.environ.get("ORACLE_INSTANTCLIENT_DIR") or "").strip()
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env))

    # Bundled next to the EXE / inside PyInstaller onefile extraction.
    candidates.append(_resource_path("instantclient_23_8"))
    candidates.append(_resource_path("instantclient"))

    # Common local install.
    candidates.append(Path(r"C:\Program Files\Oracle\instantclient_23_8"))

    # Network share used internally (same as run_ident.bat).
    candidates.append(Path(r"\\Sbureautique\sied\ndpartage\Dépendance\instantclient_23_8"))

    for candidate in candidates:
        try:
            if candidate.exists():
                return candidate
        except Exception:
            # UNC path checks can fail (offline); ignore and continue.
            continue
    return None


def _write_startup_log(error: BaseException) -> None:
    """Write startup errors to a local log file for debugging frozen builds."""
    try:
        if getattr(sys, "frozen", False):
            root = Path(sys.executable).parent
        else:
            root = Path(__file__).parent
        log_path = root / "startup_error.log"
        log_path.write_text(
            "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            encoding="utf-8",
        )
    except Exception:
        return


def _show_startup_error(error: BaseException) -> None:
    """Show a Windows message box for startup errors in frozen builds."""
    if sys.platform != "win32":
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        import ctypes

        msg = (
            "L'application n'a pas pu demarrer.\n"
            "Un journal a ete cree: startup_error.log\n\n"
            f"{error}"
        )
        ctypes.windll.user32.MessageBoxW(0, msg, "Erreur au demarrage", 0x10)
    except Exception:
        return

##############################################################################################
# L ' API CONSTITUE LES REQUETES ET LES DATA RECUPERER DANS LA DATABASE ET AFFICHE A L'ECRAN #
##############################################################################################

class Api:
    """Backend API exposed to the frontend (pywebview)."""

    def __init__(self, client: OracleClient) -> None:
        self.client = client
        self.window: Optional[webview.Window] = None
        self._cached_user: Optional[str] = ORACLE_APP_USER
        self._cached_password: Optional[str] = ORACLE_APP_PASSWORD
        self._selected_collectivite: Optional[dict] = None
        self._selected_assure_nni: Optional[str] = None
        self._logged_user: Optional[dict] = None

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
        """R?initialise le cache d'identifiants c?t? backend."""
        self._cached_user = ORACLE_APP_USER
        self._cached_password = ORACLE_APP_PASSWORD
        return {"ok": "true"}

    def login(self, identifier: str, password: str):
        identifier_value = (identifier or "").strip()
        pwd_value = (password or "").strip()
        if not identifier_value or not pwd_value:
            return {"ok": "false", "message": "Identifiant et mot de passe requis."}

        result = self.client.query_user_login(ORACLE_APP_USER, ORACLE_APP_PASSWORD, identifier_value, pwd_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de connexion : {result['error']}"}
        if not result["data"]:
            return {"ok": "false", "message": "Identifiants invalides."}

        self._logged_user = result["data"]
        return {"ok": "true", "message": "Connexion reussie.", "data": result["data"]}

    def get_logged_user(self):
        return {"ok": "true", "data": self._logged_user}

    def logout(self):
        self._logged_user = None
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

    def search_global(self, username: str, password: str, query: str, limit: int = 50):
        raw_query = (query or "").strip()
        if not raw_query:
            return {"ok": "false", "message": "Recherche vide.", "data": {"assures": [], "collectivites": []}}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": {"assures": [], "collectivites": []}}

        def parse_assure(q: str):
            if q.isdigit():
                return {"nir": q, "nom": "", "prenom": ""}
            parts = q.split()
            if len(parts) >= 2:
                return {"nir": "", "nom": parts[0], "prenom": " ".join(parts[1:])}
            return {"nir": "", "nom": q, "prenom": ""}

        def parse_collect(q: str):
            if q.isdigit():
                if len(q) == 5:
                    return {"numero": "", "denom": "", "cp": q}
                return {"numero": q, "denom": "", "cp": ""}
            return {"numero": "", "denom": q, "cp": ""}

        assure_filters = parse_assure(raw_query)
        collect_filters = parse_collect(raw_query)

        assures_result = self.client.query_assures(
            user,
            pwd,
            assure_filters["nir"],
            assure_filters["nom"],
            assure_filters["prenom"],
            order_by="nom",
        )
        collectivites_result = self.client.query_collectivites(
            user,
            pwd,
            collect_filters["numero"],
            collect_filters["denom"],
            collect_filters["cp"],
        )

        assures = assures_result["data"] if not assures_result.get("error") else []
        collectivites = collectivites_result["data"] if not collectivites_result.get("error") else []

        if limit:
            assures = assures[:limit]
            collectivites = collectivites[:limit]

        self._cached_user = user
        self._cached_password = pwd
        return {
            "ok": "true",
            "message": "Recherche globale terminée.",
            "data": {"assures": assures, "collectivites": collectivites},
        }

    def fetch_assure_situations_maladie(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_situations_maladie(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} situation(s) maladie trouvee(s).", "data": data}

    def fetch_assure_situation_maladie_current(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_situation_maladie_current(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} situation(s) maladie trouvee(s).", "data": data}

    def fetch_assure_situation_vieillesse_current(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_situation_vieillesse_current(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} situation(s) vieillesse trouvee(s).", "data": data}

    def fetch_assure_historique_situation_maladie(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_historique_situation_maladie(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} historique(s) maladie trouve(s).", "data": data}

    def fetch_assure_collectivites_maladie(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_collectivites_maladie(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} collectivite(s) maladie trouvee(s).", "data": data}

    def fetch_assure_historique_situation_vieillesse(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_historique_situation_vieillesse(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} historique(s) vieillesse trouve(s).", "data": data}

    def fetch_assure_collectivites_vieillesse(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_collectivites_vieillesse(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} collectivite(s) vieillesse trouvee(s).", "data": data}

    def fetch_assure_adresse(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_assure_adresse(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Adresse assure recuperee.", "data": result["data"]}

    def fetch_assure_ayants_droit(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_ayants_droit(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} ayant(s) droit trouve(s).", "data": data}

    def fetch_assure_arpege_summary(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": None}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": None}

        result = self.client.query_assure_arpege_summary(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": None}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Synthese ARPEGE recuperee.", "data": result["data"]}

    def fetch_assure_arpege_detail(self, username: str, password: str, nir: str):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant.", "data": []}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assure_arpege_detail(user, pwd, nir_value)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"] or []
        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} ligne(s) ARPEGE.", "data": data}

    def fetch_collectivites(self, username: str, password: str, numero: str, denom1: str, code_postal: str):
        numero_value = (numero or "").strip()
        denom1_value = (denom1 or "").strip()
        cp_value = (code_postal or "").strip()

        if not (numero_value or denom1_value or cp_value):
            return {"ok": "false", "message": "Renseignez au moins un filtre (numéro, nom, ville ou code postal).", "data": []}

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

    def fetch_referentiel_civilites(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_civilites(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Civilites recuperees.", "data": result["data"]}

    def fetch_referentiel_cultes(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_cultes(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Cultes recuperes.", "data": result["data"]}

    def fetch_referentiel_complements_num_voie(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_complements_num_voie(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Complements numero de voie recuperes.", "data": result["data"]}

    def fetch_referentiel_jod(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_jod(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "J.O.D recuperes.", "data": result["data"]}

    def fetch_referentiel_mode_vie(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_mode_vie(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Modes de vie recuperes.", "data": result["data"]}

    def fetch_referentiel_nature_situation(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_nature_situation(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Natures de situation recuperees.", "data": result["data"]}

    def fetch_referentiel_pays(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_pays(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Pays recuperes.", "data": result["data"]}

    def fetch_referentiel_situations(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_situations(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Situations recuperees.", "data": result["data"]}

    def fetch_referentiel_situations_collectivite(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_situations_collectivite(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Situations collectivite recuperees.", "data": result["data"]}

    def fetch_referentiel_type_nationalite(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_type_nationalite(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Types de nationalite recuperes.", "data": result["data"]}

    def fetch_referentiel_type_voie(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_type_voie(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Types de voie recuperes.", "data": result["data"]}

    def fetch_referentiel_societe(self, username: str, password: str):
        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_referentiel_societe(user, pwd)
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": "Societes recuperees.", "data": result["data"]}

    def export_assure(
        self,
        username: str,
        password: str,
        nir: str,
        export_mode: str = "choose",
        target_folder: str | None = None,
    ):
        nir_value = (nir or "").strip()
        if not nir_value:
            return {"ok": "false", "message": "NIR manquant pour l'export."}

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants pour l'export."}

        result = self.client.query_assures(user, pwd, nir_value, "", "")
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

        def resolve_export_dir(service: str, target_folder: str | None):
            base_dir = Path(r"\\sbureautique\SIED\dpartage\IDENT")
            mapping = {
                "JURIDIQUE": "IDENT_JUR",
                "AFFILIATION": "IDENT_AFF",
                "PCI": "IDENT_PCI",
                "RETRAITE": "IDENT_RET",
                "SIED": "IDENT_SIED",
                "AFF": "IDENT_AFF",
                "JUR": "IDENT_JUR",
                "RET": "IDENT_RET",
            }
            folder = None
            if target_folder:
                key = target_folder.strip().upper()
                folder = mapping.get(key, key)
            else:
                folder = mapping.get((service or "").strip().upper())
            if not folder:
                return None
            return base_dir / folder

        def ensure_unique_path(path: Path) -> Path:
            if not path.exists():
                return path
            stem = path.stem
            suffix = path.suffix
            idx = 1
            while True:
                candidate = path.with_name(f"{stem} ({idx}){suffix}")
                if not candidate.exists():
                    return candidate
                idx += 1

        export_mode = (export_mode or "choose").strip().lower()
        target_folder = target_folder or None

        if export_mode == "auto":
            service = (self._logged_user or {}).get("service") if self._logged_user else ""
            dest_dir = resolve_export_dir(service, target_folder)
            if not dest_dir:
                return {"ok": "false", "message": "Service inconnu pour l'export automatique."}
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                return {"ok": "false", "message": f"Echec creation dossier export : {exc}"}
            path = ensure_unique_path(dest_dir / safe_name)
        else:
            dialog_result = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename=safe_name)
            if not dialog_result:
                return {"ok": "false", "message": "Export annule."}
            path = dialog_result[0] if isinstance(dialog_result, (list, tuple)) else dialog_result
            path = str(path)
            if not path.lower().endswith(".xlsx"):
                path = f"{path}.xlsx"
        def safe_data(result, empty):
            if result.get("error"):
                return empty
            return result.get("data") or empty

        situation_maladie = safe_data(self.client.query_assure_situation_maladie_current(user, pwd, nir_value), [])
        situation_vieillesse = safe_data(self.client.query_assure_situation_vieillesse_current(user, pwd, nir_value), [])
        historique_maladie = safe_data(self.client.query_assure_historique_situation_maladie(user, pwd, nir_value), [])
        collectivites_maladie = safe_data(self.client.query_assure_collectivites_maladie(user, pwd, nir_value), [])
        historique_vieillesse = safe_data(self.client.query_assure_historique_situation_vieillesse(user, pwd, nir_value), [])
        collectivites_vieillesse = safe_data(self.client.query_assure_collectivites_vieillesse(user, pwd, nir_value), [])
        adresse = safe_data(self.client.query_assure_adresse(user, pwd, nir_value), {})
        ayants_droit = safe_data(self.client.query_assure_ayants_droit(user, pwd, nir_value), [])
        service_name = ((self._logged_user or {}).get("service") or "").strip().upper()
        include_arpege = service_name in {"RETRAITE", "SIED", "RET"}
        if include_arpege:
            arpege_summary = safe_data(self.client.query_assure_arpege_summary(user, pwd, nir_value), {})
            arpege_detail = safe_data(self.client.query_assure_arpege_detail(user, pwd, nir_value), [])
        else:
            arpege_summary = None
            arpege_detail = []

        wb = build_assure_workbook(
            first,
            situation_maladie[0] if situation_maladie else None,
            situation_vieillesse[0] if situation_vieillesse else None,
            historique_maladie,
            collectivites_maladie,
            historique_vieillesse,
            collectivites_vieillesse,
            adresse,
            ayants_droit,
            arpege_summary,
            arpege_detail,
            include_arpege,
        )
        try:
            wb.save(path)
            if not Path(path).exists():
                return {"ok": "false", "message": "Export termine mais fichier introuvable."}
            return {"ok": "true", "message": f"Export reussi : {path}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": "false", "message": f"Echec de sauvegarde : {exc}"}

    def export_collectivite(
        self,
        username: str,
        password: str,
        collect_id: str,
        export_mode: str = "choose",
        target_folder: str | None = None,
    ):
        collect_value = (collect_id or "").strip()
        if not collect_value:
            return {"ok": "false", "message": "Identifiant collectivite manquant pour l'export."}

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
        safe_name = "".join(c if c not in r'\/:*?"<>|' else "_" for c in base_name) + ".xlsx"

        if not self.window:
            return {"ok": "false", "message": "Fenetre pywebview indisponible pour ouvrir la boite de dialogue."}

        def resolve_export_dir(service: str, target: str | None):
            base_dir = Path(r"\\sbureautique\SIED\dpartage\IDENT")
            mapping = {
                "JURIDIQUE": "IDENT_JUR",
                "AFFILIATION": "IDENT_AFF",
                "PCI": "IDENT_PCI",
                "RETRAITE": "IDENT_RET",
                "SIED": "IDENT_SIED",
                "AFF": "IDENT_AFF",
                "JUR": "IDENT_JUR",
                "RET": "IDENT_RET",
            }
            folder = None
            if target:
                key = target.strip().upper()
                folder = mapping.get(key, key)
            else:
                folder = mapping.get((service or "").strip().upper())
            if not folder:
                return None
            return base_dir / folder

        def ensure_unique_path(path: Path) -> Path:
            if not path.exists():
                return path
            stem = path.stem
            suffix = path.suffix
            idx = 1
            while True:
                candidate = path.with_name(f"{stem} ({idx}){suffix}")
                if not candidate.exists():
                    return candidate
                idx += 1

        export_mode = (export_mode or "choose").strip().lower()
        target_folder = target_folder or None

        if export_mode == "auto":
            service = (self._logged_user or {}).get("service") if self._logged_user else ""
            dest_dir = resolve_export_dir(service, target_folder)
            if not dest_dir:
                return {"ok": "false", "message": "Service inconnu pour l'export automatique."}
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:  # noqa: BLE001
                return {"ok": "false", "message": f"Echec creation dossier export : {exc}"}
            path = ensure_unique_path(dest_dir / safe_name)
        else:
            dialog_result = self.window.create_file_dialog(webview.SAVE_DIALOG, save_filename=safe_name)
            if not dialog_result:
                return {"ok": "false", "message": "Export annule."}

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




#######################################################################################################
# LA PARTIE MAIN EST IMPORTANTE POUR LE LANCEMENT DE L'APPLI DE L'ENREGISTREMENT DE PARAMETRE DE BASE #
#######################################################################################################

def main() -> None:
    """Launch a native window that renders the local HTML/CSS UI."""
    _hide_console_window()
    try:
        html_path = _resource_path("templates", "login.html")
        if not html_path.exists():
            raise FileNotFoundError(f"HTML file not found: {html_path}")

        dsn = "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=CAVIMAC-ETUD2)(PORT=1521)))(CONNECT_DATA=(SERVICE_NAME=ETUDN)))"
        instant_client_dir = _find_instant_client_dir()
        client = OracleClient(dsn=dsn, instant_client_dir=instant_client_dir)
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
    except Exception as exc:  # noqa: BLE001
        _write_startup_log(exc)
        _show_startup_error(exc)
        raise


if __name__ == "__main__":
    main()
