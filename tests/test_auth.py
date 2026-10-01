from flask import Flask, jsonify
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
        user = User(email="test@example.com", name="Test User")
        user.set_password("secret123")
        db.session.add(user)
        db.session.commit()

    auth = Auth()
    auth.init_app(
        app,
        model=User,
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

    # 1. Test token login (POST /auth/token)
    res = client.post("/auth/token", json={"email": "test@example.com", "password": "secret123"})
    assert res.status_code == 200
    data = res.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    token = data["access_token"]
    refresh_token = data["refresh_token"]

    # 2. Test token_required route with Bearer token
    res = client.get("/api/protected", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.get_json()["message"] == "Hello, test@example.com"

    # 3. Test refresh token (POST /auth/refresh-token)
    res = client.post("/auth/refresh-token", json={"refresh_token": refresh_token})
    assert res.status_code == 200
    assert "access_token" in res.get_json()

    # 4. Test unauthenticated session access -> Returns 401 JSON
    res = client.get("/session/protected")
    assert res.status_code == 401
    assert res.get_json()["error"] == "Unauthorized"

    # 5. Test session login (POST /auth/session) -> Returns 200 JSON
    res = client.post("/auth/session", json={"email": "test@example.com", "password": "secret123"})
    assert res.status_code == 200
    assert res.get_json()["message"] == "Logged in successfully."

    # 6. Test session protected route after login
    res = client.get("/session/protected")
    assert res.status_code == 200
    assert res.get_json()["message"] == "Welcome test@example.com"

    # 7. Test session logout (DELETE /auth/session) -> Returns 200 JSON
    res = client.delete("/auth/session")
    assert res.status_code == 200
    assert res.get_json()["message"] == "Logged out successfully."

    # 8. Test unauthenticated session access again -> 401 JSON
    res = client.get("/session/protected")
    assert res.status_code == 401

    print("ALL JSON AUTH WORKFLOW TESTS PASSED!")


def test_auth_config_variables():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "super-secret"
    app.config["AUTH_JWT_KEY"] = "my-special-jwt-key"
    app.config["AUTH_ACCESS_EXPIRES"] = 1800
    app.config["AUTH_REFRESH_EXPIRES"] = 7200
    app.config["AUTH_COOKIE_NAME"] = "my_refresh_cookie"

    auth = Auth()
    auth.init_app(app)

    assert auth.token_manager._get_secret_key() == "my-special-jwt-key"
    assert auth.access_expires == 1800
    assert auth.refresh_expires == 7200
    assert auth.cookie_name == "my_refresh_cookie"
    print("ALL CONFIG TESTS PASSED!")


if __name__ == "__main__":
    test_auth_workflow()
    test_auth_config_variables()
