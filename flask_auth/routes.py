from flask import Blueprint, request, jsonify, make_response


def create_auth_blueprint(auth):
    bp = Blueprint("auth_endpoints", __name__)

    @bp.route("/token", methods=["POST"])
    def get_token():
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        identity = data.get("email") or data.get("identity") or data.get("username")
        password = data.get("password")

        if not identity or not password:
            return jsonify({"error": "Bad Request", "message": "Email/identity and password are required."}), 400

        user = auth.authenticate(identity, password)
        if not user:
            return jsonify({"error": "Unauthorized", "message": "Invalid credentials."}), 401

        user_id = user.get_id() if hasattr(user, "get_id") else getattr(user, "id")
        access_token = auth.create_access_token(user_id)
        refresh_token = auth.create_refresh_token(user_id)

        user_data = user.to_dict() if hasattr(user, "to_dict") else {"id": user_id}

        response_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": auth.access_expires,
            "user": user_data,
        }

        resp = make_response(jsonify(response_data), 200)

        if auth.refresh_cookie:
            resp.set_cookie(
                auth.cookie_name,
                refresh_token,
                max_age=auth.refresh_expires,
                httponly=auth.cookie_httponly,
                samesite=auth.cookie_samesite,
                secure=auth.cookie_secure,
            )

        return resp

    @bp.route("/refresh-token", methods=["POST"])
    def refresh_token_route():
        data = request.get_json(silent=True) or request.form.to_dict() or {}
        refresh_token = (
            data.get("refresh_token")
            or request.cookies.get(auth.cookie_name)
            or auth.token_manager.get_token_from_request(token_type="refresh")
        )

        if not refresh_token:
            return jsonify({"error": "Bad Request", "message": "Refresh token is missing."}), 400

        payload = auth.token_manager.decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return jsonify({"error": "Unauthorized", "message": "Invalid or expired refresh token."}), 401

        user_id = payload.get("sub")
        new_access_token = auth.create_access_token(user_id)

        return jsonify({
            "access_token": new_access_token,
            "token_type": "Bearer",
            "expires_in": auth.access_expires,
        }), 200

    @bp.route("/session", methods=["POST", "DELETE"])
    def session_route():
        if request.method == "POST":
            data = request.get_json(silent=True) or request.form.to_dict() or {}
            identity = data.get("email") or data.get("identity") or data.get("username")
            password = data.get("password")
            remember = bool(data.get("remember", False))

            if not identity or not password:
                return jsonify({"error": "Bad Request", "message": "Email/identity and password are required."}), 400

            user = auth.authenticate(identity, password)
            if not user:
                return jsonify({"error": "Unauthorized", "message": "Invalid credentials."}), 401

            auth.login_user(user, remember=remember)
            user_data = user.to_dict() if hasattr(user, "to_dict") else {"id": getattr(user, "id", None)}

            return jsonify({
                "message": "Logged in successfully.",
                "user": user_data,
            }), 200

        elif request.method == "DELETE":
            auth.logout_user()
            resp = make_response(jsonify({"message": "Logged out successfully."}), 200)
            if auth.refresh_cookie:
                resp.delete_cookie(auth.cookie_name)
            return resp

    return bp
