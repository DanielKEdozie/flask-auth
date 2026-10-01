from flask import (
    Flask,
    request,
    g,
    redirect,
    url_for,
    jsonify,
    has_request_context,
)
from flask_login import (
    LoginManager,
    login_user as flask_login_user,
    logout_user as flask_logout_user,
    login_required as flask_login_required,
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
        app=None,
        model=None,
        session_auth_redirect=None,
        session_auth_redirect_bp=None,
        session_auth_flash=None,
        session_login_redirect=None,
        session_login_flash=None,
        access_expires=3600,
        refresh_expires=604800,
        refresh_cookie=False,
        cookie_name="refresh_token",
        bp_prefix="/auth",
        register_routes=True,
        jwt_key=None,
    ):
        self.app = None
        self.model = model
        self.jwt_key = jwt_key
        self.session_auth_redirect = session_auth_redirect
        self.session_auth_redirect_bp = session_auth_redirect_bp or {}
        self.session_auth_flash = session_auth_flash
        self.session_login_redirect = session_login_redirect
        self.session_login_flash = session_login_flash
        self.access_expires = access_expires
        self.refresh_expires = refresh_expires
        self.refresh_cookie = refresh_cookie
        self.cookie_name = cookie_name
        self.bp_prefix = bp_prefix
        self.register_routes = register_routes

        self.cookie_secure = False
        self.cookie_httponly = True
        self.cookie_samesite = "Lax"

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
                session_auth_redirect=session_auth_redirect,
                session_auth_redirect_bp=session_auth_redirect_bp,
                session_auth_flash=session_auth_flash,
                session_login_redirect=session_login_redirect,
                session_login_flash=session_login_flash,
                access_expires=access_expires,
                refresh_expires=refresh_expires,
                refresh_cookie=refresh_cookie,
                cookie_name=cookie_name,
                bp_prefix=bp_prefix,
                register_routes=register_routes,
                jwt_key=jwt_key,
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
        session_auth_redirect=None,
        session_auth_redirect_bp=None,
        session_auth_flash=None,
        session_login_redirect=None,
        session_login_flash=None,
        access_expires=None,
        refresh_expires=None,
        refresh_cookie=None,
        cookie_name=None,
        bp_prefix=None,
        register_routes=None,
        jwt_key=None,
    ):
        self.app = app

        # Model
        if model is not None:
            self.model = model

        if jwt_key is not None:
            self.jwt_key = jwt_key

        # Fallbacks to app.config keys if parameter is not explicitly passed
        self.session_auth_redirect = (
            session_auth_redirect
            if session_auth_redirect is not None
            else app.config.get("AUTH_SESSION_REDIRECT", self.session_auth_redirect)
        )
        self.session_auth_redirect_bp = (
            session_auth_redirect_bp
            if session_auth_redirect_bp is not None
            else app.config.get("AUTH_SESSION_REDIRECT_BP", self.session_auth_redirect_bp)
        )
        self.session_auth_flash = (
            session_auth_flash
            if session_auth_flash is not None
            else app.config.get("AUTH_SESSION_AUTH_FLASH", self.session_auth_flash)
        )
        self.session_login_redirect = (
            session_login_redirect
            if session_login_redirect is not None
            else app.config.get("AUTH_SESSION_LOGIN_REDIRECT", self.session_login_redirect)
        )
        self.session_login_flash = (
            session_login_flash
            if session_login_flash is not None
            else app.config.get("AUTH_SESSION_LOGIN_FLASH", self.session_login_flash)
        )
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
        self.cookie_secure = app.config.get("AUTH_COOKIE_SECURE", self.cookie_secure)
        self.cookie_httponly = app.config.get("AUTH_COOKIE_HTTPONLY", self.cookie_httponly)
        self.cookie_samesite = app.config.get("AUTH_COOKIE_SAMESITE", self.cookie_samesite)

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

        # 1. Initialize Flask-Login
        self.login_manager.init_app(app)
        self.login_manager.user_loader(self.load_user)
        self.login_manager.unauthorized_handler(self._handle_unauthorized_session)

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

    def _resolve_redirect(self, target):
        if not target:
            return None
        if target.startswith("/") or target.startswith("http://") or target.startswith("https://"):
            return target
        try:
            return url_for(target)
        except Exception:
            return target

    def _do_flash(self, flash_config, default_msg="Authentication required.", default_cat="warning"):
        if not flash_config:
            return
        from flask import flash
        if isinstance(flash_config, dict):
            flash(
                flash_config.get("message", default_msg),
                flash_config.get("category", default_cat),
            )
        elif isinstance(flash_config, (list, tuple)):
            flash(flash_config[0], flash_config[1] if len(flash_config) > 1 else default_cat)
        elif isinstance(flash_config, str):
            flash(flash_config, default_cat)
        elif flash_config is True:
            flash(default_msg, default_cat)

    def _handle_unauthorized_session(self):
        current_bp = request.blueprint
        target = None

        # 1. Blueprint-specific redirect
        if current_bp and current_bp in self.session_auth_redirect_bp:
            target = self.session_auth_redirect_bp[current_bp]
        elif isinstance(self.session_auth_redirect, dict):
            target = self.session_auth_redirect.get(current_bp) or self.session_auth_redirect.get("default")
        elif isinstance(self.session_auth_redirect, str):
            target = self.session_auth_redirect

        if target:
            resolved = self._resolve_redirect(target)
            if resolved:
                self._do_flash(self.session_auth_flash, "Authentication required.", "warning")
                return redirect(resolved)

        # 2. Default JSON response
        return jsonify({"error": "Unauthorized", "message": "Authentication required."}), 401
