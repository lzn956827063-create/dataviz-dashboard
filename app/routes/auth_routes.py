"""Authentication routes."""
from flask import Blueprint, request, jsonify, g
from app.db.database import db
from app.db.models import User
from app.services.auth import create_token, login_required

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data.get("username") or not data.get("password"):
        return jsonify({"error": "Username and password required"}), 400
    if len(data["password"]) < 8:
        return jsonify({"error": "密码至少需要8位字符"}), 400
    if User.query.filter_by(username=data["username"]).first():
        return jsonify({"error": "Username already exists"}), 409
    user = User(username=data["username"])
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    token = create_token(user.id, user.username)
    return jsonify({"token": token, "user": user.to_dict()}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    password = data.get("password", "")
    if len(password) < 8:
        return jsonify({"error": "密码至少需要8位字符"}), 401
    user = User.query.filter_by(username=data.get("username", "")).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401
    token = create_token(user.id, user.username)
    return jsonify({"token": token, "user": user.to_dict()})


@auth_bp.route("/me")
@login_required
def me():
    user = User.query.get(g.user_id)
    return jsonify(user.to_dict() if user else {"error": "User not found"})
