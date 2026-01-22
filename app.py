from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import webview

from services.oracle_client import OracleClient, build_assure_workbook


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

    def fetch_assure(self, username: str, password: str, nir: str, nom: str = "", prenom: str = "", tri: str = "nir"):
        nir_value = (nir or "").strip()
        nom_value = (nom or "").strip()
        prenom_value = (prenom or "").strip()

        user, pwd = self._resolve_credentials(username, password)
        if not user or not pwd:
            return {"ok": "false", "message": "Identifiants manquants.", "data": []}

        result = self.client.query_assures(user, pwd, nir_value, nom_value, prenom_value, order_by=tri or "nir")
        if result["error"]:
            return {"ok": "false", "message": f"Echec de recuperation : {result['error']}", "data": []}

        data = result["data"]
        if not data:
            return {"ok": "false", "message": "Aucun assure trouve pour ce motif NIR.", "data": []}

        self._cached_user = user
        self._cached_password = pwd
        return {"ok": "true", "message": f"{len(data)} assure(s) trouve(s).", "data": data}

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

        path = dialog_result[0]
        wb = build_assure_workbook(data)
        try:
            wb.save(path)
            return {"ok": "true", "message": f"Export reussi : {path}"}
        except Exception as exc:  # noqa: BLE001
            return {"ok": "false", "message": f"Echec de sauvegarde : {exc}"}


def main() -> None:
    """Launch a native window that renders the local HTML/CSS UI."""
    root = Path(__file__).parent
    html_path = root / "templates" / "index.html"
    if not html_path.exists():
        raise FileNotFoundError(f"HTML file not found: {html_path}")

    dsn = "(DESCRIPTION=(ADDRESS_LIST=(ADDRESS=(PROTOCOL=TCP)(HOST=CAVIMAC-ETUD2)(PORT=1521)))(CONNECT_DATA=(SERVICE_NAME=ETUDN)))"
    instant_client_dir = Path(r"C:\Program Files\Oracle\instantclient_23_8")
    client = OracleClient(dsn=dsn, instant_client_dir=instant_client_dir if instant_client_dir.exists() else None)
    api = Api(client=client)

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
