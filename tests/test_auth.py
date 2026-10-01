from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_auth import Auth, UserMixin, current_user


def test_auth_workflow():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "super-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True

    db = SQLAlchemy(app)

    class User(UserMixin, db.Model):
        __tablename__ = "users"
        name = db.Column(db.String(50))

    with app.app_context():
        db.create_all()
        # Seed test user
        user = User(email="test@example.com", name="Test User")
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    auth = Auth()
    auth.init_app(
        app,
        model=User,
        session_auth_redirect="/login",
        session_auth_redirect_bp={"admin": "/admin/login"},
        access_expires=3600,
        refresh_expires=86400,
        refresh_cookie=True,
    )

    @app.route("/api/protected")
    @auth.token_required
    def protected_api():
        return jsonify({"message": f"Hello, {current_user.email}"})

    @app.route("/session/protected")
    @auth.login_required
    def protected_session():
        return jsonify({"message": f"Welcome {current_user.email}"})

    client = app.test_client()

    # 1. Test token login
    res = client.post("/auth/token", json={"email": "test@example.com", "password": "secret123"})
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 2. Test token_required route
    res = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["message"] == "Hello, test@example.com"

    # 3. Test refresh token
    res = client.post("/auth/refresh-token", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    new_token = res.get_json()["access_token"]
    assert new_token is not None

    # 4. Test session login & logout
    res = client.post("/auth/session", json={"email": "test@example.com", "password": "secret123"})
    assert res.status_code == 200

    res = client.get("/session/protected")
    assert res.status_code == 200
    assert res.get_json()["message"] == "Welcome test@example.com"

    res = client.delete("/auth/session")
    assert res.status_code == 200

    # 5. Test redirect on unauthenticated session
    res = client.get("/session/protected")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    print("ALL WORKFLOW TESTS PASSED!")


def test_auth_config_variables():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "super-secret"
    app.config["AUTH_JWT_KEY"] = "my-special-jwt-key"
    app.config["AUTH_ACCESS_EXPIRES"] = 1800
    app.config["AUTH_REFRESH_EXPIRES"] = 7200
    app.config["AUTH_COOKIE_NAME"] = "my_refresh_cookie"
    app.config["AUTH_SESSION_REDIRECT"] = "/custom-login"
    app.config["AUTH_SESSION_REDIRECT_BP"] = {"admin": "/custom-admin-login"}

    auth = Auth()
    auth.init_app(app)

    assert auth.token_manager._get_secret_key() == "my-special-jwt-key"
    assert auth.access_expires == 1800
    assert auth.refresh_expires == 7200
    assert auth.cookie_name == "my_refresh_cookie"
    assert auth.session_auth_redirect == "/custom-login"
    assert auth.session_auth_redirect_bp == {"admin": "/custom-admin-login"}
    print("ALL CONFIG TESTS PASSED!")


def test_session_login_redirect_and_flash():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "super-secret"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True

    db = SQLAlchemy(app)

    class User(UserMixin, db.Model):
        __tablename__ = "users_test2"
        name = db.Column(db.String(50))

    with app.app_context():
        db.create_all()
        user = User(email="redirect_user@example.com", name="Redirect User")
        user.set_password("pass123")
        db.session.add(user)
        db.session.commit()

    # 1. Test single string redirect + flash
    auth = Auth()
    auth.init_app(
        app,
        model=User,
        session_login_redirect="/dashboard",
        session_login_flash={"message": "Welcome back!", "category": "success"},
    )

    client = app.test_client()
    res = client.post("/auth/session", json={"email": "redirect_user@example.com", "password": "pass123"})
    assert res.status_code == 302
    assert "/dashboard" in res.headers["Location"]

    # 2. Test blueprint dictionary redirect
    auth.session_login_redirect = {"admin": "/admin/dashboard", "default": "/user/home"}

    # With blueprint in json body
    res = client.post("/auth/session", json={"email": "redirect_user@example.com", "password": "pass123", "blueprint": "admin"})
    assert res.status_code == 302
    assert "/admin/dashboard" in res.headers["Location"]

    # With default
    res = client.post("/auth/session", json={"email": "redirect_user@example.com", "password": "pass123"})
    assert res.status_code == 302
    assert "/user/home" in res.headers["Location"]

    print("ALL SESSION REDIRECT & FLASH TESTS PASSED!")


if __name__ == "__main__":
    test_auth_workflow()
    test_auth_config_variables()
    test_session_login_redirect_and_flash()

