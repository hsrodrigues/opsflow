"""Configuração de implantação — pedido explícito do cliente: "por uma tela
pra eu mesmo fazer essa configuração sem precisar mexer dentro do código".

Ferramenta STANDALONE, de propósito: edita `DATABASE_URL`/`JWT_SECRET` no
`.env` da raiz do projeto — exatamente o que o backend precisa pra sequer
conseguir subir. Por isso não pode ser uma tela dentro do app principal
(login/dashboard/console de plataforma): todas essas telas já dependem de
uma API rodando, que por sua vez já depende do `.env` estar configurado.
Rode com `python desktop/tools/deployment_config.py` (funciona a partir de
qualquer diretório — ver o `sys.path`/caminho do `.env` abaixo).

Depois de salvar, é preciso REINICIAR o backend (`uvicorn`) pra nova
configuração ter efeito — o processo já rodando não relê o `.env` sozinho.
"""
import logging
import re
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

DESKTOP_DIR = Path(__file__).resolve().parents[1]
if str(DESKTOP_DIR) not in sys.path:
    sys.path.insert(0, str(DESKTOP_DIR))

ENV_PATH = DESKTOP_DIR.parent / ".env"
ENV_EXAMPLE_PATH = DESKTOP_DIR.parent / ".env.example"

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.theme import apply_shadow, apply_theme  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("opsflow.deployment_config")

_DATABASE_URL_RE = re.compile(r"^DATABASE_URL=(.*)$", re.MULTILINE)
_JWT_SECRET_RE = re.compile(r"^JWT_SECRET=(.*)$", re.MULTILINE)


def _read_env_text() -> str:
    if ENV_PATH.is_file():
        return ENV_PATH.read_text(encoding="utf-8")
    if ENV_EXAMPLE_PATH.is_file():
        # Primeira vez rodando isto sem nenhum .env ainda — parte do exemplo
        # versionado, do mesmo jeito que o setup manual documentado no README.
        return ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    return ""


def _parse_database_url(url: str) -> dict:
    if not url:
        return {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "", "database": "opsflow_db"}
    scheme, _, rest = url.partition("://")
    parsed = urlparse(f"{scheme.split('+', 1)[0]}://{rest}")
    return {
        "host": parsed.hostname or "127.0.0.1", "port": parsed.port or 3306,
        "user": unquote(parsed.username or "root"), "password": unquote(parsed.password or ""),
        "database": parsed.path.lstrip("/") or "opsflow_db",
    }


def _build_database_url(*, host: str, port: int, user: str, password: str, database: str) -> str:
    # `safe=""`: por padrão `quote()` deixa "/" sem escapar (é seu uso mais
    # comum, separador de caminho) — mas usuário/senha podem legitimamente
    # conter "/" (ou "@", ":"), e um "/" sem escapar aqui quebra o parsing
    # de volta em `_parse_database_url` (o `urlparse` interpreta como um
    # separador de path no meio do userinfo). Bug real, pego testando o
    # ciclo completo salvar->reabrir com uma senha desse tipo.
    safe_user = quote(user, safe="")
    safe_password = quote(password, safe="")
    return f"mysql+pymysql://{safe_user}:{safe_password}@{host}:{port}/{database}"


def _upsert_line(text: str, pattern: re.Pattern, key: str, value: str) -> str:
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    separator = "" if text.endswith("\n") or not text else "\n"
    return f"{text}{separator}{line}\n"


class DeploymentConfigWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("AppRoot")
        self.setWindowTitle("OpsFlow — Configuração de Implantação")
        self.resize(560, 640)
        self._build_ui()
        self._load_current_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        layout.addWidget(QLabel("Configuração de implantação", objectName="PageTitle"))
        layout.addWidget(QLabel(
            "Aponte o OpsFlow pra outro banco MySQL (ex.: um serviço na nuvem) sem "
            "precisar editar arquivo nenhum na mão. Depois de salvar, reinicie o backend.",
            objectName="Muted",
        ))

        self._status_message = QLabel("")
        self._status_message.setObjectName("Muted")
        self._status_message.setWordWrap(True)
        self._status_message.hide()
        layout.addWidget(self._status_message)

        # --- cartão do banco de dados ---
        db_card = QFrame(objectName="Card")
        apply_shadow(db_card, blur=20, y_offset=6, alpha=16)
        db_layout = QVBoxLayout(db_card)
        db_layout.setContentsMargins(20, 18, 20, 18)
        db_layout.setSpacing(12)
        db_layout.addWidget(QLabel("Banco de dados (MySQL)", objectName="SectionTitle"))

        form = QFormLayout()
        form.setSpacing(10)
        self._host_input = QLineEdit()
        self._host_input.setPlaceholderText("ex.: bxxxxx-mysql.services.clever-cloud.com")
        form.addRow("Host *", self._host_input)

        self._port_input = QSpinBox()
        self._port_input.setRange(1, 65535)
        self._port_input.setValue(3306)
        form.addRow("Porta *", self._port_input)

        self._user_input = QLineEdit()
        form.addRow("Usuário *", self._user_input)

        self._password_input = QLineEdit()
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha", self._password_input)

        self._database_input = QLineEdit()
        form.addRow("Nome do banco *", self._database_input)
        db_layout.addLayout(form)

        db_buttons_row = QHBoxLayout()
        test_button = QPushButton("Testar conexão", objectName="SecondaryButton")
        test_button.clicked.connect(self._handle_test_connection_clicked)
        db_buttons_row.addWidget(test_button)
        db_buttons_row.addStretch(1)
        save_button = QPushButton("Salvar", objectName="PrimaryButton")
        save_button.clicked.connect(self._handle_save_database_clicked)
        db_buttons_row.addWidget(save_button)
        db_layout.addLayout(db_buttons_row)
        layout.addWidget(db_card)

        # --- cartão do segredo JWT ---
        jwt_card = QFrame(objectName="Card")
        apply_shadow(jwt_card, blur=20, y_offset=6, alpha=16)
        jwt_layout = QVBoxLayout(jwt_card)
        jwt_layout.setContentsMargins(20, 18, 20, 18)
        jwt_layout.setSpacing(8)
        jwt_layout.addWidget(QLabel("Segredo de autenticação (JWT_SECRET)", objectName="SectionTitle"))
        self._jwt_status_label = QLabel("", objectName="Muted")
        self._jwt_status_label.setWordWrap(True)
        jwt_layout.addWidget(self._jwt_status_label)
        regenerate_button = QPushButton("Gerar novo segredo", objectName="SecondaryButton")
        regenerate_button.clicked.connect(self._handle_regenerate_jwt_clicked)
        jwt_layout.addWidget(regenerate_button)
        layout.addWidget(jwt_card)

        layout.addStretch(1)
        path_label = QLabel(f"Arquivo: {ENV_PATH}", objectName="Faint")
        layout.addWidget(path_label)

    def _load_current_values(self) -> None:
        text = _read_env_text()
        match = _DATABASE_URL_RE.search(text)
        values = _parse_database_url(match.group(1).strip() if match else "")
        self._host_input.setText(values["host"])
        self._port_input.setValue(values["port"])
        self._user_input.setText(values["user"])
        self._password_input.setText(values["password"])
        self._database_input.setText(values["database"])

        jwt_match = _JWT_SECRET_RE.search(text)
        has_jwt = bool(jwt_match and jwt_match.group(1).strip())
        self._jwt_status_label.setText(
            "Já configurado (valor não é exibido por segurança)." if has_jwt
            else "⚠ Ainda não configurado — obrigatório antes de usar em produção."
        )

    def _collect_database_values(self) -> dict | None:
        host = self._host_input.text().strip()
        user = self._user_input.text().strip()
        database = self._database_input.text().strip()
        if not host or not user or not database:
            self._show_status("Preencha host, usuário e nome do banco.", is_error=True)
            return None
        return {
            "host": host, "port": self._port_input.value(), "user": user,
            "password": self._password_input.text(), "database": database,
        }

    def _handle_test_connection_clicked(self) -> None:
        values = self._collect_database_values()
        if values is None:
            return
        try:
            import pymysql

            connection = pymysql.connect(
                host=values["host"], port=values["port"], user=values["user"], password=values["password"],
                database=values["database"], connect_timeout=8,
            )
            connection.close()
            self._show_status(f"✓ Conexão OK com \"{values['database']}\" em {values['host']}.")
        except Exception as exc:  # noqa: BLE001 - qualquer falha de conexão vira uma mensagem amigável
            self._show_status(f"Não foi possível conectar: {exc}", is_error=True)

    def _handle_save_database_clicked(self) -> None:
        values = self._collect_database_values()
        if values is None:
            return
        new_url = _build_database_url(**values)
        text = _read_env_text()
        text = _upsert_line(text, _DATABASE_URL_RE, "DATABASE_URL", new_url)
        ENV_PATH.write_text(text, encoding="utf-8")
        logger.info("DATABASE_URL atualizado em %s (host=%s, db=%s)", ENV_PATH, values["host"], values["database"])
        self._show_status(
            "Configuração salva. Reinicie o backend (uvicorn) para aplicar — "
            "ele só lê o .env na inicialização."
        )

    def _handle_regenerate_jwt_clicked(self) -> None:
        confirmation = QMessageBox.question(
            self, "Gerar novo segredo",
            "Isso desconecta TODOS os usuários logados agora (todo mundo precisa "
            "entrar de novo) — o token de cada um foi assinado com o segredo antigo.\n\n"
            "Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        new_secret = secrets.token_urlsafe(64)
        text = _read_env_text()
        text = _upsert_line(text, _JWT_SECRET_RE, "JWT_SECRET", new_secret)
        ENV_PATH.write_text(text, encoding="utf-8")
        logger.info("JWT_SECRET regenerado em %s", ENV_PATH)
        self._jwt_status_label.setText("Já configurado (valor não é exibido por segurança).")
        self._show_status("Novo segredo salvo. Reinicie o backend para aplicar.")

    def _show_status(self, message: str, *, is_error: bool = False) -> None:
        self._status_message.setObjectName("ErrorBanner" if is_error else "Muted")
        self._status_message.style().unpolish(self._status_message)
        self._status_message.style().polish(self._status_message)
        self._status_message.setText(message)
        self._status_message.show()


def main() -> int:
    app = QApplication(sys.argv)
    apply_theme(app, dark=False)
    window = DeploymentConfigWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
