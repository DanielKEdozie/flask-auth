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
    print("ALL TESTS PASSED!")


if __name__ == "__main__":
    test_auth_workflow()
