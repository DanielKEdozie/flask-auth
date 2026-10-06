from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_auth import Auth, UserMixin


def create_test_cli_app(cli_extra_fields=None):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = "secret-key"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True

    db = SQLAlchemy(app)

    class CustomUser(UserMixin, db.Model):
        __tablename__ = "users"
        name = db.Column(db.String(64), nullable=False)
        role = db.Column(db.String(64), nullable=True)
        phone = db.Column(db.String(32), nullable=True)

    auth = Auth()
    auth.init_app(
        app,
        model=CustomUser,
        cli_extra_fields=cli_extra_fields or {
            "name": {
                "args": "--name",
                "prompt": "Enter user name",
                "placeholder": "Default Name",
                "required": True,
            },
            "phone": {
                "args": "--phone",
                "prompt": "Enter phone number",
                "placeholder": "555-0199",
            }
        }
    )

    with app.app_context():
        db.create_all()

    return app, db, CustomUser, auth


def test_cli_suite():
    app, db, CustomUser, auth = create_test_cli_app()
    runner = app.test_cli_runner()

    # 1. Test create with explicit --name and --phone
    res = runner.invoke(
        args=["auth", "create", "--email", "alice@example.com", "--password", "pass123", "--name", "Alice Wonderland", "--phone", "111-222"]
    )
    assert res.exit_code == 0, res.output
    assert "Successfully created user 'alice@example.com'" in res.output

    with app.app_context():
        user = CustomUser.query.filter_by(email="alice@example.com").first()
        assert user is not None
        assert user.name == "Alice Wonderland"
        assert user.phone == "111-222"
        assert user.verify_password("pass123")

    # 2. Test create with non-interactive placeholder fallback when --name omitted on required field
    res = runner.invoke(
        args=["auth", "create", "--email", "bob@example.com", "--password", "pass123"]
    )
    assert res.exit_code == 0, res.output
    assert "Successfully created user 'bob@example.com'" in res.output

    with app.app_context():
        user = CustomUser.query.filter_by(email="bob@example.com").first()
        assert user is not None
        # Placeholder was "Default Name"
        assert user.name == "Default Name"
        assert user.phone == "555-0199"

    # 3. Test create with extra field using -f
    res = runner.invoke(
        args=["auth", "create", "--email", "charlie@example.com", "--password", "pass123", "--name", "Charlie", "-f", "role=engineer"]
    )
    assert res.exit_code == 0, res.output
    with app.app_context():
        user = CustomUser.query.filter_by(email="charlie@example.com").first()
        assert user is not None
        assert user.role == "engineer"

    # 4. Test create with arbitrary flag --role
    res = runner.invoke(
        args=["auth", "create", "--email", "dave@example.com", "--password", "pass123", "--name", "Dave", "--role", "manager"]
    )
    assert res.exit_code == 0, res.output
    with app.app_context():
        user = CustomUser.query.filter_by(email="dave@example.com").first()
        assert user is not None
        assert user.role == "manager"

    # 5. Test auth list
    res = runner.invoke(args=["auth", "list"])
    assert res.exit_code == 0, res.output
    assert "alice@example.com" in res.output
    assert "bob@example.com" in res.output

    # 6. Test auth update
    res = runner.invoke(
        args=["auth", "update", "--email", "alice@example.com", "--name", "Alice New", "--admin"]
    )
    assert res.exit_code == 0, res.output
    with app.app_context():
        user = CustomUser.query.filter_by(email="alice@example.com").first()
        assert user.name == "Alice New"
        assert user.is_admin is True

    # 7. Test auth set-password
    res = runner.invoke(
        args=["auth", "set-password", "--email", "alice@example.com", "--password", "newpassword"]
    )
    assert res.exit_code == 0, res.output
    with app.app_context():
        user = CustomUser.query.filter_by(email="alice@example.com").first()
        assert user.verify_password("newpassword")

    # 8. Test auth delete
    res = runner.invoke(
        args=["auth", "delete", "--email", "bob@example.com", "--yes"]
    )
    assert res.exit_code == 0, res.output
    with app.app_context():
        user = CustomUser.query.filter_by(email="bob@example.com").first()
        assert user is None

    print("ALL CLI SUITE TESTS PASSED!")


if __name__ == "__main__":
    test_cli_suite()
