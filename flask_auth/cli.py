import click
from flask.cli import AppGroup


def _normalize_cli_extra_fields(cli_extra_fields):
    """
    Normalizes cli_extra_fields dict:
    {
        field_name: {
            'args': '--flag' or ['-f', '--flag'],
            'prompt': 'Prompt message' or True,
            'placeholder': 'Default/placeholder value',
            'required': bool,
            'help': 'Help description',
            'type': type
        }
    }
    """
    normalized = {}
    if not cli_extra_fields or not isinstance(cli_extra_fields, dict):
        return normalized

    for field, cfg in cli_extra_fields.items():
        if isinstance(cfg, str):
            cfg = {"prompt": cfg}
        elif not isinstance(cfg, dict):
            cfg = {}

        raw_args = cfg.get("args") or ""
        if isinstance(raw_args, (list, tuple)):
            flags = list(raw_args)
        elif isinstance(raw_args, str) and raw_args.strip():
            flags = [f.strip() for f in raw_args.split() if f.strip()]
        else:
            flags = [f"--{field.replace('_', '-')}"]

        prompt = cfg.get("prompt")
        placeholder = cfg.get("placeholder", cfg.get("default", None))
        required = bool(cfg.get("required", False))
        help_text = cfg.get("help", f"User {field.replace('_', ' ')}.")
        field_type = cfg.get("type", str)

        normalized[field] = {
            "flags": flags,
            "prompt": prompt,
            "placeholder": placeholder,
            "required": required,
            "help": help_text,
            "type": field_type,
        }
    return normalized


def _inspect_model_columns(model):
    """
    Inspect model columns to identify all defined columns and which columns are required.
    Returns:
        columns_dict: {col_name: col_obj}
        required_names: set of column names that cannot be null and have no default.
    """
    if not model:
        return {}, set()

    columns = {}
    try:
        from sqlalchemy import inspect as sa_inspect
        mapper = sa_inspect(model)
        for c in mapper.columns:
            columns[c.key] = c
    except Exception:
        table = getattr(model, "__table__", None)
        if table is not None and hasattr(table, "columns"):
            for c in table.columns:
                columns[c.name] = c

    # System / UserMixin managed fields that shouldn't be prompted as missing
    ignored = {"id", "email", "password_hash", "is_active", "is_admin"}
    required_names = set()

    for name, col in columns.items():
        if name in ignored or getattr(col, "primary_key", False):
            continue
        is_nullable = getattr(col, "nullable", True)
        has_default = getattr(col, "default", None) is not None
        has_server_default = getattr(col, "server_default", None) is not None
        if not is_nullable and not has_default and not has_server_default:
            required_names.add(name)

    return columns, required_names


def _coerce_field_value(col, value, field_type=None):
    """Attempt type conversion based on column type or configured field type."""
    if value is None:
        return None

    if field_type is not None and field_type is not str:
        try:
            if field_type is bool and isinstance(value, str):
                return value.lower() in ("true", "1", "yes", "y", "t")
            return field_type(value)
        except (ValueError, TypeError):
            pass

    if col is None:
        return value

    col_type = getattr(col, "type", None)
    if col_type is None:
        return value
    type_str = str(col_type).lower()
    if "int" in type_str:
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    if "bool" in type_str:
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "y", "t")
        return bool(value)
    if "float" in type_str or "numeric" in type_str:
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    return value


def _parse_cli_extra_args(args):
    """
    Parse arbitrary unknown flags from context args (e.g. ['--role', 'admin', '--phone=123']).
    """
    extra = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            cleaned = arg[2:]
            if "=" in cleaned:
                k, v = cleaned.split("=", 1)
                extra[k.replace("-", "_")] = v
            elif i + 1 < len(args) and not args[i + 1].startswith("-"):
                extra[cleaned.replace("-", "_")] = args[i + 1]
                i += 1
            else:
                extra[cleaned.replace("-", "_")] = True
        i += 1
    return extra


def create_auth_cli(auth):
    auth_cli = AppGroup("auth", help="Flask-Auth user management commands.")
    cli_extra_fields = _normalize_cli_extra_fields(getattr(auth, "cli_extra_fields", {}))

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

    def _create_user_cmd(ctx, email, password, name, admin, active, fields, **extra_kwargs):
        """Create a new user with support for custom and required fields."""
        model = auth.model
        if not model:
            click.secho("Error: No User model configured with Auth.", fg="red")
            return

        db = _get_db()
        existing = _find_user(email)
        if existing:
            click.secho(f"Error: User with email '{email}' already exists.", fg="red")
            return

        columns, model_required_cols = _inspect_model_columns(model)

        # 1. Gather all extra field inputs
        extra_fields = {}
        for k, v in extra_kwargs.items():
            if v is not None:
                extra_fields[k] = v

        for k, v in _parse_cli_extra_args(ctx.args).items():
            if k not in extra_fields or extra_fields[k] is None:
                extra_fields[k] = v

        for item in fields:
            if "=" in item:
                k, v = item.split("=", 1)
                extra_fields[k.strip().replace("-", "_")] = v.strip()

        if name is not None:
            extra_fields["name"] = name

        # 2. Determine all required fields
        cfg_required = {
            f for f, cfg in cli_extra_fields.items() if cfg.get("required")
        }
        auth_required = set(getattr(auth, "cli_required_fields", []) or [])
        all_required = model_required_cols | cfg_required | auth_required

        is_interactive = False
        try:
            is_interactive = click.get_text_stream("stdin").isatty()
        except Exception:
            is_interactive = False

        # 3. Handle configured cli_extra_fields (prompts, placeholders, requirements)
        for field_name, cfg in cli_extra_fields.items():
            if field_name not in extra_fields or extra_fields[field_name] is None:
                custom_prompt = cfg.get("prompt")
                placeholder = cfg.get("placeholder")
                is_req = field_name in all_required

                # If prompt is explicitly configured OR field is required
                if custom_prompt or is_req:
                    prompt_label = (
                        custom_prompt
                        if (isinstance(custom_prompt, str) and custom_prompt.strip())
                        else f"User {field_name.replace('_', ' ').title()}"
                    )
                    default_val = placeholder
                    if not default_val and field_name in ("name", "username"):
                        default_val = email.split("@")[0]

                    if is_interactive:
                        if default_val is not None and default_val != "":
                            val = click.prompt(prompt_label, default=default_val)
                        else:
                            val = click.prompt(prompt_label)
                        extra_fields[field_name] = val
                    else:
                        if default_val is not None and default_val != "":
                            extra_fields[field_name] = default_val
                        elif is_req:
                            try:
                                extra_fields[field_name] = click.prompt(prompt_label)
                            except Exception:
                                click.secho(
                                    f"Error: Missing required field '{field_name}'. "
                                    f"Provide it using --{field_name.replace('_', '-')} or -f {field_name}=value.",
                                    fg="red",
                                )
                                return

        # 4. Handle remaining required columns from model inspection
        for req_field in sorted(all_required):
            if req_field not in extra_fields or extra_fields[req_field] is None:
                default_val = email.split("@")[0] if req_field in ("name", "username") else None
                label = f"User {req_field.replace('_', ' ').title()}"
                if is_interactive:
                    if default_val:
                        val = click.prompt(label, default=default_val)
                    else:
                        val = click.prompt(label)
                    extra_fields[req_field] = val
                else:
                    if default_val is not None:
                        extra_fields[req_field] = default_val
                    else:
                        try:
                            extra_fields[req_field] = click.prompt(label)
                        except Exception:
                            click.secho(
                                f"Error: Missing required field '{req_field}'. "
                                f"Provide it using --{req_field.replace('_', '-')} or -f {req_field}=value.",
                                fg="red",
                            )
                            return

        # 5. Fallback for 'name' if model has 'name' attribute or column
        if ("name" not in extra_fields or extra_fields["name"] is None) and (hasattr(model, "name") or "name" in columns):
            if is_interactive:
                extra_fields["name"] = click.prompt("User name", default=email.split("@")[0])
            else:
                extra_fields["name"] = email.split("@")[0]

        # 6. Build model kwargs
        kwargs = {"email": email}
        if hasattr(model, "is_admin"):
            kwargs["is_admin"] = admin
        if hasattr(model, "is_active"):
            kwargs["is_active"] = active

        for k, v in extra_fields.items():
            if v is None:
                continue
            col = columns.get(k)
            field_type = cli_extra_fields.get(k, {}).get("type")
            coerced_v = _coerce_field_value(col, v, field_type=field_type)
            kwargs[k] = coerced_v

        try:
            user = model(**kwargs)
        except TypeError:
            filtered_kwargs = {
                k: v for k, v in kwargs.items()
                if hasattr(model, k) or k in columns or k in ("email", "is_admin", "is_active")
            }
            try:
                user = model(**filtered_kwargs)
            except Exception as e:
                click.secho(f"Error instantiating {model.__name__}: {e}", fg="red")
                return

        if hasattr(user, "set_password"):
            user.set_password(password)
        elif hasattr(user, "password"):
            user.password = password

        if db:
            try:
                db.session.add(user)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                click.secho(f"Error saving user to database: {e}", fg="red")
                return
        elif hasattr(user, "save"):
            try:
                user.save()
            except Exception as e:
                click.secho(f"Error saving user: {e}", fg="red")
                return

        admin_tag = " (Admin)" if admin else ""
        click.secho(f"Successfully created user '{email}'{admin_tag}.", fg="green")

    # Build create command with standard options and dynamic extra field options
    cmd_func = _create_user_cmd
    default_names = {"email", "password", "name", "admin", "active", "fields"}
    for f_name, f_cfg in cli_extra_fields.items():
        if f_name not in default_names:
            cmd_func = click.option(
                *f_cfg["flags"],
                f_name,
                default=None,
                help=f_cfg["help"],
            )(cmd_func)

    cmd_func = click.option("-f", "--field", "fields", multiple=True, help="Additional user field in key=value format.")(cmd_func)
    cmd_func = click.option("--active/--inactive", default=True, help="Set user active status (default: active).")(cmd_func)
    cmd_func = click.option("--admin", is_flag=True, default=False, help="Grant admin privileges.")(cmd_func)
    cmd_func = click.option("--name", default=None, help="User display name.")(cmd_func)
    cmd_func = click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True, help="User password.")(cmd_func)
    cmd_func = click.option("--email", prompt=True, help="User email address.")(cmd_func)
    cmd_func = click.pass_context(cmd_func)

    auth_cli.command(
        "create",
        context_settings=dict(ignore_unknown_options=True, allow_extra_args=True),
        help="Create a new user with support for custom and required fields."
    )(cmd_func)

    @auth_cli.command("update", context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
    @click.pass_context
    @click.option("--email", prompt=True, help="User email address to update.")
    @click.option("--name", default=None, help="Update display name.")
    @click.option("--admin/--no-admin", default=None, help="Update admin privileges.")
    @click.option("--active/--inactive", default=None, help="Update active status.")
    @click.option("-f", "--field", "fields", multiple=True, help="Additional fields to update in key=value format.")
    def update_user_cmd(ctx, email, name, admin, active, fields):
        """Update existing user attributes."""
        user = _find_user(email)
        if not user:
            click.secho(f"Error: User '{email}' not found.", fg="red")
            return

        model = auth.model
        columns, _ = _inspect_model_columns(model)

        extra_fields = _parse_cli_extra_args(ctx.args)
        for item in fields:
            if "=" in item:
                k, v = item.split("=", 1)
                extra_fields[k.strip().replace("-", "_")] = v.strip()

        if name is not None:
            extra_fields["name"] = name
        if admin is not None and hasattr(user, "is_admin"):
            user.is_admin = admin
        if active is not None and hasattr(user, "is_active"):
            user.is_active = active

        for k, v in extra_fields.items():
            if hasattr(user, k):
                col = columns.get(k)
                setattr(user, k, _coerce_field_value(col, v))

        db = _get_db()
        if db:
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                click.secho(f"Error updating user: {e}", fg="red")
                return
        elif hasattr(user, "save"):
            user.save()
        elif hasattr(user, "update"):
            user.update()

        click.secho(f"Successfully updated user '{email}'.", fg="green")

    @auth_cli.command("list")
    def list_users_cmd():
        """List all users."""
        model = auth.model
        if not model:
            click.secho("Error: No User model registered with Auth extension.", fg="red")
            return

        db = _get_db()
        users = []
        if hasattr(model, "query"):
            users = model.query.all()
        elif db:
            stmt = db.select(model)
            users = db.session.execute(stmt).scalars().all()

        if not users:
            click.echo("No users found.")
            return

        click.secho(f"Found {len(users)} user(s):", fg="cyan", bold=True)
        for u in users:
            uid = getattr(u, "id", "-")
            uemail = getattr(u, "email", "-")
            uname = getattr(u, "name", None)
            is_admin = getattr(u, "is_admin", False)
            is_active = getattr(u, "is_active", True)
            flags = []
            if is_admin:
                flags.append("Admin")
            if not is_active:
                flags.append("Inactive")
            flag_str = f" [{', '.join(flags)}]" if flags else ""
            name_str = f" ({uname})" if uname else ""
            click.echo(f"  #{uid} {uemail}{name_str}{flag_str}")

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
            try:
                db.session.delete(user)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                click.secho(f"Error deleting user: {e}", fg="red")
                return
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
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                click.secho(f"Error updating password: {e}", fg="red")
                return
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
