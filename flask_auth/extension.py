from typing import Optional
from flask import (
    Flask,
    request,
    g,
    jsonify,
    has_request_context,
)
from flask_login import (
    LoginManager,
    login_required as flask_login_required,
    login_user as flask_login_user,
    logout_user as flask_logout_user,
    current_user as flask_login_current_user,
)
from flask_httpauth import HTTPTokenAuth
from werkzeug.local import LocalProxy

from .tokens import TokenManager
from .mixins import UserMixin


def _get_unified_current_user():
    if not has_request_context():
        return None
    # 1. Check if token auth loaded a user into g
    token_user = getattr(g, "_auth_token_user", None)
    if token_user is not None:
        return token_user
    # 2. Check if Flask-Login has an authenticated session user
    if flask_login_current_user and flask_login_current_user.is_authenticated:
        return flask_login_current_user
    return flask_login_current_user


current_user = LocalProxy(_get_unified_current_user)


class Auth:
    def __init__(
        self,
        app: Optional[Flask] = None,
        model=None,
        access_expires: int = 3600,
        refresh_expires: int = 604800,
        refresh_cookie: bool = False,
        cookie_name: str = "refresh_token",
        cookie_secure: bool = False,
        cookie_httponly: bool = True,
        cookie_samesite: str = "Lax",
        bp_prefix: str = "/auth",
        register_routes: bool = True,
        jwt_key=None,
        cli_extra_fields=None,
        cli_required_fields=None,
        cli_fields=None,
    ):
        self.app = app
        self.model = model
        self.jwt_key = jwt_key
        self.access_expires = access_expires
        self.refresh_expires = refresh_expires
        self.refresh_cookie = refresh_cookie
        self.cookie_name = cookie_name
        self.cookie_secure = cookie_secure
        self.cookie_httponly = cookie_httponly
        self.cookie_samesite = cookie_samesite
        self.bp_prefix = bp_prefix
        self.register_routes = register_routes
        self.cli_extra_fields = cli_extra_fields or {}
        self.cli_required_fields = cli_required_fields or []
        self.cli_fields = cli_fields or []

        # Underlying extensions
        self.login_manager = LoginManager()
        self.http_auth = HTTPTokenAuth(scheme="Bearer")
        self.token_manager = None

        self._user_loader_callback = None
        self._authenticate_callback = None

        # Expose decorators and methods
        self.login_required = flask_login_required
        self.token_required = self.http_auth.login_required
        self.login_user = flask_login_user
        self.logout_user = flask_logout_user

        if app is not None:
            self.init_app(
                app,
                model=model,
                access_expires=access_expires,
                refresh_expires=refresh_expires,
                refresh_cookie=refresh_cookie,
                cookie_name=cookie_name,
                cookie_secure=cookie_secure,
                cookie_httponly=cookie_httponly,
                cookie_samesite=cookie_samesite,
                bp_prefix=bp_prefix,
                register_routes=register_routes,
                jwt_key=jwt_key,
                cli_extra_fields=cli_extra_fields,
                cli_required_fields=cli_required_fields,
                cli_fields=cli_fields,
            )

    @property
    def current_user(self):
        return current_user

    def user_loader(self, callback):
        """Custom user loader callback: user_loader(user_id) -> user"""
        self._user_loader_callback = callback
        return callback

    def authenticate_handler(self, callback):
        """Custom authentication callback: authenticate_handler(identity, password) -> user"""
        self._authenticate_callback = callback
        return callback

    def init_app(
        self,
        app: Flask,
        model=None,
        access_expires=None,
        refresh_expires=None,
        refresh_cookie=None,
        cookie_name=None,
        cookie_secure=None,
        cookie_httponly=None,
        cookie_samesite=None,
        bp_prefix=None,
        register_routes=None,
        jwt_key=None,
        cli_extra_fields=None,
        cli_required_fields=None,
        cli_fields=None,
    ):
        self.app = app

        if model is not None:
            self.model = model

        if jwt_key is not None:
            self.jwt_key = jwt_key

        self.cli_extra_fields = (
            cli_extra_fields
            if cli_extra_fields is not None
            else app.config.get("AUTH_CLI_EXTRA_FIELDS", self.cli_extra_fields)
        )
        self.cli_required_fields = (
            cli_required_fields
            if cli_required_fields is not None
            else app.config.get("AUTH_CLI_REQUIRED_FIELDS", self.cli_required_fields)
        )
        self.cli_fields = (
            cli_fields
            if cli_fields is not None
            else app.config.get("AUTH_CLI_FIELDS", self.cli_fields)
        )

        # Configuration fallbacks
        self.access_expires = (
            access_expires
            if access_expires is not None
            else app.config.get("AUTH_ACCESS_EXPIRES", self.access_expires)
        )
        self.refresh_expires = (
            refresh_expires
            if refresh_expires is not None
            else app.config.get("AUTH_REFRESH_EXPIRES", self.refresh_expires)
        )
        self.refresh_cookie = (
            refresh_cookie
            if refresh_cookie is not None
            else app.config.get("AUTH_REFRESH_COOKIE", self.refresh_cookie)
        )
        self.cookie_name = (
            cookie_name
            if cookie_name is not None
            else app.config.get("AUTH_COOKIE_NAME", self.cookie_name)
        )
        self.cookie_secure = (
            cookie_secure
            if cookie_secure is not None
            else app.config.get("AUTH_COOKIE_SECURE", self.cookie_secure)
        )
        self.cookie_httponly = (
            cookie_httponly
            if cookie_httponly is not None
            else app.config.get("AUTH_COOKIE_HTTPONLY", self.cookie_httponly)
        )
        self.cookie_samesite = (
            cookie_samesite
            if cookie_samesite is not None
            else app.config.get("AUTH_COOKIE_SAMESITE", self.cookie_samesite)
        )

        self.bp_prefix = (
            bp_prefix
            if bp_prefix is not None
            else app.config.get("AUTH_BP_PREFIX", self.bp_prefix)
        )
        self.register_routes = (
            register_routes
            if register_routes is not None
            else app.config.get("AUTH_REGISTER_ROUTES", self.register_routes)
        )

        secret_key = (
            self.jwt_key
            or app.config.get("AUTH_JWT_KEY")
            or app.config.get("AUTH_SECRET_KEY")
            or app.config.get("SECRET_KEY", "flask-auth-secret")
        )
        algorithm = app.config.get("AUTH_ALGORITHM", "HS256")

        self.token_manager = TokenManager(
            secret_key=secret_key,
            algorithm=algorithm,
            access_expires=self.access_expires,
            refresh_expires=self.refresh_expires,
        )

        # 1. Initialize Flask-Login (Always returns 401 JSON when unauthorized)
        self.login_manager.init_app(app)
        self.login_manager.user_loader(self.load_user)

        @self.login_manager.unauthorized_handler
        def _handle_unauthorized():
            return jsonify({"error": "Unauthorized", "message": "Authentication required."}), 401

        # 2. Initialize Flask-HTTPAuth
        @self.http_auth.verify_token
        def _verify_token(token):
            if not token:
                return None
            payload = self.token_manager.decode_token(token)
            if not payload or payload.get("type") != "access":
                return None
            user = self.load_user(payload.get("sub"))
            if user:
                g._auth_token_user = user
                return user
            return None

        @self.http_auth.error_handler
        def _token_error_handler(status):
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired token."}), status

        app.extensions = getattr(app, "extensions", {})
        app.extensions["flask_auth"] = self

        # 3. Register routes
        if self.register_routes:
            from .routes import create_auth_blueprint
            bp = create_auth_blueprint(self)
            app.register_blueprint(bp, url_prefix=self.bp_prefix)

        # 4. Register CLI commands
        from .cli import create_auth_cli
        app.cli.add_command(create_auth_cli(self))

    def load_user(self, user_id):
        if self._user_loader_callback:
            return self._user_loader_callback(user_id)
        if self.model:
            try:
                user_id_int = int(user_id)
            except (ValueError, TypeError):
                user_id_int = user_id

            if hasattr(self.model, "query") and hasattr(self.model.query, "get"):
                user = self.model.query.get(user_id_int)
                if user:
                    return user
            if hasattr(self.app, "extensions") and "sqlalchemy" in self.app.extensions:
                db = self.app.extensions["sqlalchemy"]
                return db.session.get(self.model, user_id_int)
        return None

    def authenticate(self, identity, password):
        if self._authenticate_callback:
            return self._authenticate_callback(identity, password)

        if not self.model:
            return None

        user = None
        if hasattr(self.model, "query"):
            if hasattr(self.model, "email"):
                user = self.model.query.filter_by(email=identity).first()
            elif hasattr(self.model, "username"):
                user = self.model.query.filter_by(username=identity).first()
        elif hasattr(self.app, "extensions") and "sqlalchemy" in self.app.extensions:
            db = self.app.extensions["sqlalchemy"]
            if hasattr(self.model, "email"):
                stmt = db.select(self.model).where(self.model.email == identity)
                user = db.session.execute(stmt).scalar_one_or_none()

        if user and hasattr(user, "verify_password") and user.verify_password(password):
            return user
        return None

    def create_access_token(self, identity, extra_claims=None, expires_in=None):
        return self.token_manager.create_access_token(identity, extra_claims=extra_claims, expires_in=expires_in)

    def create_refresh_token(self, identity, extra_claims=None, expires_in=None):
        return self.token_manager.create_refresh_token(identity, extra_claims=extra_claims, expires_in=expires_in)
