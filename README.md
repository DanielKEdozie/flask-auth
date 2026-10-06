# flask-auth

A clean, API-first authentication extension for Flask that bridges **Flask-Login** (session-based authentication) and **Flask-HTTPAuth** (JWT token-based authentication), returning consistent JSON responses across all auth flows.

## Features

- **Dual-Mode Authentication**: Seamlessly support both Session and Token (Bearer JWT) authentication.
- **Flask-Login Under the Hood**: Uses `LoginManager`, `login_user()`, `logout_user()`, and `login_required`.
- **Flask-HTTPAuth Under the Hood**: Uses `HTTPTokenAuth` with `@auth.token_required`.
- **Pure JSON Responses**: Clean and decoupled. Unauthorized requests return standard `401 Unauthorized` JSON so blueprints/frontends handle UI redirection and messaging based on HTTP status codes.
- **Extensible `UserMixin`**: Preconfigured with SQLAlchemy columns (`id`, `email`, `password_hash`, `is_active`, `is_admin`) and password verification methods (`set_password`, `verify_password`).
- **Unified `current_user`**: Context proxy resolving the active user whether authenticated via JWT or session.
- **Built-in Endpoints**: Ready-to-use routes for `/auth/token`, `/auth/refresh-token`, and `/auth/session`.
- **Intelligent User CLI**: Rich Click CLI for creating, managing, updating, and deleting users with automated SQLAlchemy model inspection, required field prompts, and arbitrary field support.

## Installation

```bash
pip install git+https://github.com/DanielKEdozie/flask-auth.git
```

## Quick Start

```python
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_auth import Auth, UserMixin, current_user

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key"
app.config["AUTH_JWT_KEY"] = "dedicated-jwt-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///app.db"

db = SQLAlchemy(app)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    name = db.Column(db.String(100), nullable=False)

auth = Auth()
auth.init_app(
    app,
    model=User,
    access_expires=3600,
    refresh_expires=604800,
    refresh_cookie=True,
)

# Protected API route (Bearer JWT)
@app.route("/api/profile")
@auth.token_required
def api_profile():
    return jsonify({"user": current_user.to_dict()})

# Protected Session route (Cookie)
@app.route("/api/session/profile")
@auth.login_required
def session_profile():
    return jsonify({"user": current_user.to_dict()})
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
| `AUTH_BP_PREFIX` | `"/auth"` | URL prefix for built-in authentication routes |
| `AUTH_REGISTER_ROUTES` | `True` | Set to `False` to disable built-in routes |
| `AUTH_CLI_REQUIRED_FIELDS` | `[]` | List of field names that the CLI should require when creating users |
| `AUTH_CLI_FIELDS` | `[]` | List of additional field names supported by the CLI |

## Built-in Endpoints

- `POST /auth/token`: Body `{ "email": "...", "password": "..." }` -> Returns `{ access_token, refresh_token, token_type, expires_in, user }` (200) or 401.
- `POST /auth/refresh-token`: Returns new access token `{ access_token, token_type, expires_in }` (200) or 401.
- `POST /auth/session`: Body `{ "email": "...", "password": "..." }` -> Returns `{ message: "Logged in successfully.", user }` (200) or 401.
- `DELETE /auth/session`: Clears session -> Returns `{ message: "Logged out successfully." }` (200).

## CLI Configuration (`cli_extra_fields`)

You can define custom CLI fields, custom prompt text, CLI flags, and default placeholders on `Auth` initialization:

```python
auth.init_app(
    app,
    model=User,
    cli_extra_fields={
        "name": {
            "args": "--name",
            "prompt": "Enter user full name",
            "placeholder": "Default Name",
            "required": True,
        },
        "phone": {
            "args": "--phone",
            "prompt": "Enter phone number",
            "placeholder": "555-0100",
        },
    },
)
```

| Property | Type | Description |
|---|---|---|
| `args` | `str` or `list` | CLI option flag(s) (e.g. `"--name"` or `"-n --name"`). Defaults to `"--<field-name>"`. |
| `prompt` | `str` or `bool` | Custom interactive prompt message shown when field is omitted. |
| `placeholder` | `str` or `any` | Default placeholder value used during prompt or non-interactive CLI fallback. |
| `required` | `bool` | Whether the field is mandatory when creating users. |

## CLI Commands

Flask-Auth registers user management commands with the `flask` CLI:

```bash
# Create a standard user (interactive prompts for password and missing required fields if omitted)
flask auth create --email user@example.com --password secret

# Create user with display name
flask auth create --email user@example.com --password secret --name "Jane Doe"

# Create an administrator
flask auth create --email admin@example.com --password secret --admin

# Provide custom or additional model fields via -f / --field or direct flags
flask auth create --email user@example.com --password secret -f role=manager -f department=Finance
flask auth create --email user@example.com --password secret --role manager

# Automatically handles required non-nullable fields on your custom User model:
# (e.g. if User model requires `name`, interactive mode prompts for it,
# while non-interactive scripts fall back to email username or accept --name)

# List all users
flask auth list

# Update existing user attributes
flask auth update --email user@example.com --name "New Name" --admin
flask auth update --email user@example.com -f role=supervisor

# Update or reset user password
flask auth set-password --email user@example.com --password newsecret
flask auth reset-password --email user@example.com --password newsecret

# Delete a user
flask auth delete --email user@example.com
flask auth delete --email user@example.com --yes
```

## License

MIT
