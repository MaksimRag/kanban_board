from flask import Blueprint, jsonify, request
from pymongo.errors import DuplicateKeyError
import db

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.route("/", methods=["GET"])
def list_users():
    return jsonify(db.list_users())


@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    user = db.get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@users_bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    email = data.get("email")

    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "Field 'username' is required"}), 400
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "Field 'email' is required"}), 400

    try:
        user = db.create_user(
            username=username.strip(),
            email=email.strip(),
            password_hash=data.get("password_hash", ""),
            full_name=data.get("full_name"),
        )
    except DuplicateKeyError:
        return jsonify({"error": "User with this username or email already exists"}), 409

    return jsonify(user), 201


@users_bp.route("/<user_id>", methods=["PATCH", "PUT"])
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    try:
        user = db.update_user(user_id, **data)
    except DuplicateKeyError:
        return jsonify({"error": "Username or email is already in use"}), 409
    if user is None:
        return jsonify({"error": "User not found or invalid id"}), 404
    return jsonify(user)


@users_bp.route("/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    if not db.delete_user(user_id):
        return jsonify({"error": "User not found or invalid id"}), 404
    return "", 204