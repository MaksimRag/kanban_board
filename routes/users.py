from flask import Blueprint, jsonify, request
import db

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/", methods=["GET"])
def list_users():
    return jsonify(db.list_users())


@users_bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json() or {}
    user = db.create_user(
        username=data["username"],
        email=data["email"],
        password_hash=data.get("password_hash", ""),  # позже — хеширование
        full_name=data.get("full_name"),
    )
    return jsonify(user), 201