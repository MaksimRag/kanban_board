from flask import Blueprint, jsonify, request, session
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash
import db

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _public_user(user):
    if not user:
        return user
    return {key: value for key, value in user.items() if key != "password_hash"}


@users_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}

    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    full_name = data.get("full_name", "")

    if not all(isinstance(value, str) for value in (username, email, password, full_name)):
        return jsonify({"error": "Все поля должны содержать текстовые значения"}), 400

    username = username.strip()
    email = email.strip().lower()
    full_name = " ".join(full_name.split())

    if not full_name:
        return jsonify({"error": "Введите ФИО"}), 400
    if len(full_name) < 5 or not re.fullmatch(r"[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё\\s-]*", full_name):
        return jsonify({"error": "Проверьте ФИО: используйте буквы, пробелы и дефис"}), 400
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        return jsonify({"error": "Логин должен содержать 3–30 символов: латинские буквы, цифры или _"}), 400
    if len(email) > 254 or not re.fullmatch(r"[^\\s@]+@[^\\s@]+\\.[^\\s@]+", email):
        return jsonify({"error": "Введите корректный адрес электронной почты"}), 400
    if len(password) < 8:
        return jsonify({"error": "Пароль должен содержать не менее 8 символов"}), 400
    if len(password) > 128:
        return jsonify({"error": "Пароль слишком длинный (максимум 128 символов)"}), 400

    try:
        user = db.create_user(username, email, generate_password_hash(password), full_name)
    except DuplicateKeyError:
        return jsonify({"error": "Пользователь с таким логином или email уже существует"}), 409

    return jsonify({"message": "Регистрация прошла успешно. Теперь войдите в систему."}), 201

@users_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    login_value = data.get("login", "").strip()
    password = data.get("password", "")
    if not login_value or not password:
        return jsonify({"error": "Введите логин/email и пароль"}), 400

    user = db.get_user_by_email(login_value.lower()) or db.get_user_by_username(login_value)
    if user is None or not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Неверный логин/email или пароль"}), 401

    session.clear()
    session["user_id"] = user["_id"]
    session["username"] = user["username"]
    return jsonify({"message": "Вход выполнен", "user": _public_user(user)})


@users_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Вы вышли из системы"})


@users_bp.route("/", methods=["GET"])
def list_users():
    return jsonify([_public_user(user) for user in db.list_users()])


@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    user = db.get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(_public_user(user))


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
        user = db.create_user(username.strip(), email.strip().lower(), "", data.get("full_name"))
    except DuplicateKeyError:
        return jsonify({"error": "User with this username or email already exists"}), 409
    return jsonify(_public_user(user)), 201


@users_bp.route("/<user_id>", methods=["PATCH", "PUT"])
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    data.pop("password_hash", None)
    try:
        user = db.update_user(user_id, **data)
    except DuplicateKeyError:
        return jsonify({"error": "Username or email is already in use"}), 409
    if user is None:
        return jsonify({"error": "User not found or invalid id"}), 404
    return jsonify(_public_user(user))


@users_bp.route("/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    if session.get("user_id") == user_id:
        return jsonify({"error": "Нельзя удалить текущую учётную запись"}), 400
    if not db.delete_user(user_id):
        return jsonify({"error": "User not found or invalid id"}), 404
    return "", 204
