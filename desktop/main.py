"""OpsFlow Desktop — entry point.

Run with `python main.py` from inside `desktop/` (or `python desktop/main.py`
from the repo root — both work, see the `sys.path` setup below).
"""
import logging
import sys
from pathlib import Path

DESKTOP_DIR = Path(__file__).resolve().parent
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.assets import icon_path  # noqa: E402
from app.config import load_config  # noqa: E402
from app.session import UserSession  # noqa: E402
from services.api_client import ApiClient  # noqa: E402
from ui.login_window import LoginWindow  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402
from ui.platform_window import PlatformWindow  # noqa: E402
from ui.theme import apply_theme  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger("opsflow.desktop")


class AppController:
    """Owns the currently visible window and swaps login <-> main shell.

    A plain module-level `main()` would let PySide6 garbage-collect a
    window the moment its local variable goes out of scope, silently
    closing it — keeping both windows as attributes here is what keeps them
    alive for the life of the app.
    """

    def __init__(self, app: QApplication) -> None:
        self._app = app
        self._config = load_config()
        self._api_client = ApiClient(self._config)
        self._session = UserSession()
        self._dark_mode = False
        self.login_window: LoginWindow | None = None
        self.main_window: MainWindow | PlatformWindow | None = None

        apply_theme(self._app, dark=self._dark_mode)
        self._show_login()

    def _apply_theme(self, *, dark: bool) -> None:
        self._dark_mode = dark
        apply_theme(self._app, dark=dark)

    def _show_login(self) -> None:
        self.main_window = None
        self.login_window = LoginWindow(
            self._config, self._api_client, self._session, self._handle_login_success, self._apply_theme,
        )
        self.login_window.showMaximized()

    def _handle_login_success(self) -> None:
        logger.info("Login bem-sucedido: user_id=%s tenant_id=%s", self._session.user_id, self._session.tenant_id)
        if self.login_window is not None:
            self.login_window.close()
            self.login_window = None
        # `tenant_id is None` só acontece pra SUPER_ADMIN (seção 54) — um
        # usuário de plataforma, não de uma empresa cliente. O shell normal
        # (sidebar de cadastros/operação) não faz sentido pra esse papel, daí
        # a janela diferente em vez de mostrar telas que dariam 403 em tudo.
        window_class = PlatformWindow if self._session.tenant_id is None else MainWindow
        self.main_window = window_class(
            self._config, self._api_client, self._session, self._handle_logout, self._apply_theme,
        )
        self.main_window.showMaximized()

    def _handle_logout(self) -> None:
        logger.info("Logout: user_id=%s", self._session.user_id)
        self._session.clear()
        if self.main_window is not None:
            self.main_window.close()
        self._show_login()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("OpsFlow")
    app.setOrganizationName("OpsFlow")
    if icon_path().is_file():
        app.setWindowIcon(QIcon(str(icon_path())))
    controller = AppController(app)
    exit_code = app.exec()
    controller._api_client.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
