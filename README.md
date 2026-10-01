# flask-auth

A unified authentication extension for Flask that bridges **Flask-Login** (session-based authentication) and **Flask-HTTPAuth** (JWT token-based authentication).

## Features

- **Dual-Mode Authentication**: Seamlessly support both Session and Token (Bearer JWT) authentication.
- **Flask-Login Under the Hood**: Uses `LoginManager`, `login_user()`, `logout_user()`, and `login_required`.
- **Flask-HTTPAuth Under the Hood**: Uses `HTTPTokenAuth` with `@auth.token_required`.
- **Blueprint-Aware Redirection**: Configurable redirect targets per blueprint (`session_auth_redirect_bp`) with automatic fallback to global redirect or a 401 JSON response.
- **Extensible `UserMixin`**: Preconfigured with SQLAlchemy columns (`id`, `email`, `password_hash`, `is_active`, `is_admin`) and password verification methods (`set_password`, `verify_password`).
- **Unified `current_user`**: Context proxy resolving user whether authenticated via JWT or session.
- **Built-in Endpoints**: Ready-to-use routes for `/auth/token`, `/auth/refresh-token`, and `/auth/session`.

## Installation

```bash
pip install git+https://github.com/DanielKEdozie/flask-auth.git
```

## Quick Start

```python
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_auth import Auth, UserMixin, current_user

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"

db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    name = db.Column(db.String(100))

auth = Auth()
auth.init_app(
    app,
    model=User,
    session_auth_redirect="/login",
    session_auth_redirect_bp={
        "admin": "/admin/login",
    },
    access_expires=3600,
    refresh_expires=604800,
    refresh_cookie=True,
)

# API Route (Bearer Token)
@app.route("/api/profile")
@auth.token_required
def api_profile():
    return {"user": current_user.to_dict()}

# Web Route (Session Cookie)
@app.route("/dashboard")
@auth.login_required
def dashboard():
    return f"Welcome {current_user.email}"
```

## Configuration

You can configure `flask-auth` using standard `app.config` variables:

| Setting | Default | Description |
|---|---|---|
| `AUTH_JWT_KEY` | `None` (falls back to `AUTH_SECRET_KEY` / `SECRET_KEY`) | Dedicated secret key used for signing JWT tokens |
| `AUTH_SECRET_KEY` | `SECRET_KEY` | Secret key used for signing JWT tokens (if `AUTH_JWT_KEY` not set) |
| `AUTH_ALGORITHM` | `"HS256"` | JWT algorithm |
| `AUTH_ACCESS_EXPIRES` | `3600` | Access token lifespan in seconds |
| `AUTH_REFRESH_EXPIRES` | `604800` | Refresh token lifespan in seconds (7 days) |
| `AUTH_REFRESH_COOKIE` | `False` | Whether to send refresh token in an HttpOnly cookie |
| `AUTH_COOKIE_NAME` | `"refresh_token"` | Name of the refresh cookie |
| `AUTH_COOKIE_SECURE` | `False` | Send cookie over HTTPS only |
| `AUTH_COOKIE_HTTPONLY` | `True` | Disallow JavaScript access to cookie |
| `AUTH_COOKIE_SAMESITE` | `"Lax"` | SameSite cookie policy (`"Lax"`, `"Strict"`, `"None"`) |
| `AUTH_SESSION_REDIRECT` | `None` | Redirect target for unauthorized session requests (single path or blueprint dict) |
| `AUTH_SESSION_REDIRECT_BP` | `{}` | Blueprint-to-redirect mapping for unauthorized session requests |
| `AUTH_SESSION_AUTH_FLASH` | `None` | Flash notification when unauthorized session redirect triggers (e.g. `{"message": "Please log in", "category": "warning"}`) |
| `AUTH_SESSION_LOGIN_REDIRECT` | `None` | Post-login redirect target (single path or blueprint dict like `{"admin": "/admin", "default": "/"}`) |
| `AUTH_SESSION_LOGIN_FLASH` | `None` | Flash notification upon successful session login (e.g. `{"message": "Welcome back!", "category": "success"}`) |
| `AUTH_BP_PREFIX` | `"/auth"` | URL prefix for built-in authentication routes |
| `AUTH_REGISTER_ROUTES` | `True` | Set to `False` to disable built-in routes |

## Built-in Endpoints

- `POST /auth/token`: Body `{ "email": "...", "password": "..." }` -> Returns `{ access_token, refresh_token, ... }`.
- `POST /auth/refresh-token`: Returns new access token.
- `POST /auth/session`: Session login.
- `DELETE /auth/session`: Session logout.

## License

MIT
