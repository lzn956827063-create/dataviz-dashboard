"""JWT authentication service."""
import os
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import request, jsonify, current_app, g

SECRET = os.getenv("JWT_SECRET", "dataviz-jwt-secret-dev")
EXPIRY_HOURS = 24


def create_token(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRY_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid token"}), 401

        payload = decode_token(auth[7:])
        if payload is None:
            return jsonify({"error": "Token expired or invalid"}), 401

        g.user_id = payload["sub"]
        g.username = payload["username"]
        return f(*args, **kwargs)

    return decorated


def optional_login(f):
    """Like login_required, but allows unauthenticated access (sets g.user_id to None)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            payload = decode_token(auth[7:])
            if payload:
                g.user_id = payload["sub"]
                g.username = payload["username"]
                return f(*args, **kwargs)
        g.user_id = None
        g.username = None
        return f(*args, **kwargs)

    return decorated
