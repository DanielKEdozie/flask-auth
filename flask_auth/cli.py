import click
from flask.cli import AppGroup


def create_auth_cli(auth):
    auth_cli = AppGroup("auth", help="Flask-Auth user management commands.")

    def _get_db():
        if hasattr(auth.app, "extensions") and "sqlalchemy" in auth.app.extensions:
            return auth.app.extensions["sqlalchemy"]
        from flask import current_app
        return current_app.extensions.get("sqlalchemy")

    def _find_user(email):
        model = auth.model
        if not model:
            click.secho("Error: No User model registered with Auth extension.", fg="red")
            return None
        db = _get_db()
        if hasattr(model, "query"):
            return model.query.filter_by(email=email).first()
        elif db:
            stmt = db.select(model).where(model.email == email)
            return db.session.execute(stmt).scalar_one_or_none()
        return None

    @auth_cli.command("create")
    @click.option("--email", prompt=True, help="User email address.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="User password.")
    @click.option("--admin", is_flag=True, default=False, help="Grant admin privileges.")
    @click.option("--name", default=None, help="User display name.")
    def create_user_cmd(email, password, admin, name):
        """Create a new user."""
        model = auth.model
        if not model:
            click.secho("Error: No User model configured with Auth.", fg="red")
            return

        db = _get_db()
        existing = _find_user(email)
        if existing:
            click.secho(f"Error: User with email '{email}' already exists.", fg="red")
            return

        kwargs = {"email": email}
        if name and hasattr(model, "name"):
            kwargs["name"] = name
        elif hasattr(model, "name"):
            kwargs["name"] = email.split("@")[0]

        if hasattr(model, "is_admin"):
            kwargs["is_admin"] = admin

        user = model(**kwargs)
        if hasattr(user, "set_password"):
            user.set_password(password)
        elif hasattr(user, "password"):
            user.password = password

        if db:
            db.session.add(user)
            db.session.commit()
        elif hasattr(user, "save"):
            user.save()

        admin_tag = " (Admin)" if admin else ""
        click.secho(f"Successfully created user '{email}'{admin_tag}.", fg="green")

    @auth_cli.command("delete")
    @click.option("--email", prompt=True, help="User email address to delete.")
    @click.option("--yes", "-y", is_flag=True, default=False, help="Confirm deletion without prompting.")
    def delete_user_cmd(email, yes):
        """Delete an existing user."""
        user = _find_user(email)
        if not user:
            click.secho(f"Error: User '{email}' not found.", fg="red")
            return

        if not yes and not click.confirm(f"Are you sure you want to delete user '{email}'?"):
            click.echo("Cancelled.")
            return

        db = _get_db()
        if db:
            db.session.delete(user)
            db.session.commit()
        elif hasattr(user, "delete"):
            user.delete()

        click.secho(f"Successfully deleted user '{email}'.", fg="green")

    def _set_user_password(email, password):
        user = _find_user(email)
        if not user:
            click.secho(f"Error: User '{email}' not found.", fg="red")
            return

        if hasattr(user, "set_password"):
            user.set_password(password)
        elif hasattr(user, "password"):
            user.password = password

        db = _get_db()
        if db:
            db.session.commit()
        elif hasattr(user, "update"):
            user.update()

        click.secho(f"Password for user '{email}' updated successfully.", fg="green")

    @auth_cli.command("set-password")
    @click.option("--email", prompt=True, help="User email address.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="New password.")
    def set_password_cmd(email, password):
        """Set or change user password."""
        _set_user_password(email, password)

    @auth_cli.command("reset-password")
    @click.option("--email", prompt=True, help="User email address.")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="New password.")
    def reset_password_cmd(email, password):
        """Reset user password (alias for set-password)."""
        _set_user_password(email, password)

    return auth_cli
