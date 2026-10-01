import datetime
from datetime import timezone
import jwt
from flask import current_app, request


class TokenManager:
    def __init__(self, secret_key=None, algorithm="HS256", access_expires=3600, refresh_expires=604800):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_expires = access_expires
        self.refresh_expires = refresh_expires

    def _get_secret_key(self):
        return self.secret_key or current_app.config.get("SECRET_KEY", "flask-auth-secret-key")

    def create_token(self, identity, token_type="access", expires_in=None, extra_claims=None):
        if expires_in is None:
            expires_in = self.access_expires if token_type == "access" else self.refresh_expires

        now = datetime.datetime.now(timezone.utc)
        payload = {
            "sub": identity,
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int((now + datetime.timedelta(seconds=expires_in)).timestamp()),
        }
        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(payload, self._get_secret_key(), algorithm=self.algorithm)

    def create_access_token(self, identity, extra_claims=None, expires_in=None):
        return self.create_token(identity, token_type="access", expires_in=expires_in, extra_claims=extra_claims)

    def create_refresh_token(self, identity, extra_claims=None, expires_in=None):
        return self.create_token(identity, token_type="refresh", expires_in=expires_in, extra_claims=extra_claims)

    def decode_token(self, token):
        try:
            return jwt.decode(token, self._get_secret_key(), algorithms=[self.algorithm])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    def get_token_from_request(self, token_type="access", cookie_name=None):
        # 1. Authorization header: Bearer <token>
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return auth_header.split(" ", 1)[1].strip()

        # 2. Cookie lookup if provided or configured
        if cookie_name:
            cookie_val = request.cookies.get(cookie_name)
            if cookie_val:
                return cookie_val

        return None
