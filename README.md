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

## Built-in Endpoints

- `POST /auth/token`: Body `{ "email": "...", "password": "..." }` -> Returns `{ access_token, refresh_token, ... }`.
- `POST /auth/refresh-token`: Returns new access token.
- `POST /auth/session`: Session login.
- `DELETE /auth/session`: Session logout.

## License

MIT
