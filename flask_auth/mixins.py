from flask_login import UserMixin as FlaskLoginUserMixin
from werkzeug.security import generate_password_hash, check_password_hash

try:
    from sqlalchemy.orm import declared_attr, Mapped, mapped_column
    from sqlalchemy import Integer, String, Boolean
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False


class UserMixin(FlaskLoginUserMixin):
    """
    Combines Flask-Login's UserMixin with SQLAlchemy columns and password helpers.
    Extend this class in your app's User model to add custom fields and relationships.
    """
    if HAS_SQLALCHEMY:
        @declared_attr
        def id(cls) -> Mapped[int]:
            return mapped_column(Integer, primary_key=True)

        @declared_attr
        def email(cls) -> Mapped[str]:
            return mapped_column(String(120), unique=True, nullable=False, index=True)

        @declared_attr
        def password_hash(cls) -> Mapped[str]:
            return mapped_column(String(255), nullable=False)

        @declared_attr
        def is_active(cls) -> Mapped[bool]:
            return mapped_column(Boolean, default=True)

        @declared_attr
        def is_admin(cls) -> Mapped[bool]:
            return mapped_column(Boolean, default=False)

    @property
    def password(self):
        raise AttributeError("Password is write-only.")

    @password.setter
    def password(self, plain_password):
        self.set_password(plain_password)

    def set_password(self, plain_password):
        self.password_hash = generate_password_hash(plain_password)

    def verify_password(self, plain_password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, plain_password)

    def to_dict(self):
        return {
            "id": getattr(self, "id", None),
            "email": getattr(self, "email", None),
            "is_active": getattr(self, "is_active", True),
            "is_admin": getattr(self, "is_admin", False),
        }
