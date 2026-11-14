import re

from flask import Blueprint, jsonify, request, session
from pymongo.errors import DuplicateKeyError
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

import db


users_bp = Blueprint("users", __name__, url_prefix="/users")




def _can_manage_participants():
    """Владелец хотя бы одного проекта может управлять общим списком участников."""
    user_id = session.get("user_id")
    return bool(user_id and db.list_projects(owner_id=user_id))


def _owner_required():
    if not _can_manage_participants():
        return jsonify({"error": "Управлять участниками может только владелец проекта"}), 403
    return None


def _public_user(user):
    if not user:
        return user
    return {key: value for key, value in user.items() if key != "password_hash"}


@users_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Некорректные данные формы"}), 400

    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    full_name = data.get("full_name") or ""

    if not all(isinstance(value, str) for value in (username, email, password, full_name)):
        return jsonify({"error": "Проверьте введённые данные"}), 400

    username = username.strip()
    email = email.strip().lower()
    full_name = " ".join(full_name.split())

    # ФИО необязательно. Если поле заполнено, проверяем его формат.
    if full_name and (
        len(full_name) < 5
        or len(full_name) > 100
        or not re.fullmatch(r"[A-Za-zА-Яа-яЁё -]+", full_name)
        or len(full_name.split()) < 2
    ):
        return jsonify({"error": "Если указываете ФИО, введите фамилию и имя буквами"}), 400
    if not full_name:
        full_name = None
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        return jsonify({"error": "Логин должен содержать 3–30 символов: латинские буквы, цифры или _"}), 400
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify({"error": "Введите корректный адрес электронной почты"}), 400
    if len(password) < 8:
        return jsonify({"error": "Пароль должен содержать не менее 8 символов"}), 400
    if len(password) > 128:
        return jsonify({"error": "Пароль слишком длинный (максимум 128 символов)"}), 400

    try:
        db.create_user(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
            full_name=full_name,
        )
    except DuplicateKeyError:
        return jsonify({"error": "Пользователь с таким логином или email уже существует"}), 409
    except Exception:
        return jsonify({"error": "Не удалось выполнить регистрацию. Попробуйте позже"}), 500

    return jsonify({
        "message": "Вы успешно зарегистрированы. Теперь войдите в систему."
    }), 201


@users_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Некорректные данные формы"}), 400

    login_value = data.get("login", "")
    password = data.get("password", "")

    if not isinstance(login_value, str) or not isinstance(password, str):
        return jsonify({"error": "Проверьте логин и пароль"}), 400

    login_value = login_value.strip()
    if not login_value or not password:
        return jsonify({"error": "Введите логин/email и пароль"}), 400

    try:
        user = db.get_user_by_email(login_value.lower())
        if user is None:
            user = db.get_user_by_username(login_value)
    except Exception:
        return jsonify({"error": "Не удалось связаться с базой данных. Попробуйте позже"}), 500

    if (
        user is None
        or not user.get("password_hash")
        or not check_password_hash(user["password_hash"], password)
    ):
        return jsonify({"error": "Неверный логин/email или пароль"}), 401

    session.clear()
    session["user_id"] = user["_id"]
    session["username"] = user["username"]
    return jsonify({"message": "Вход выполнен"}), 200


@users_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Вы вышли из системы"}), 200


@users_bp.route("/", methods=["GET"])
def list_users():
    return jsonify([_public_user(user) for user in db.list_users()])


@users_bp.route("/me", methods=["GET"])
def current_user():
    """Возвращает данные пользователя из текущей сессии."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Необходимо войти в аккаунт"}), 401

    user = db.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return jsonify({"error": "Пользователь не найден. Войдите в аккаунт повторно."}), 404

    return jsonify({
        "username": user.get("username", ""),
        "full_name": user.get("full_name") or "",
        "email": user.get("email", ""),
    }), 200


@users_bp.route("/me", methods=["PATCH"])
def update_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Необходимо войти в аккаунт"}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    username = data.get("username", "")
    email = data.get("email", "")
    full_name = data.get("full_name", "")

    if not all(isinstance(value, str) for value in (current_password, username, email, full_name)):
        return jsonify({"error": "Проверьте введённые данные"}), 400

    user = db.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return jsonify({"error": "Пользователь не найден. Войдите в аккаунт повторно."}), 404
    if not user.get("password_hash") or not check_password_hash(user["password_hash"], current_password):
        return jsonify({"error": "Для изменения профиля введите действующий пароль"}), 400

    username = username.strip()
    email = email.strip().lower()
    full_name = " ".join(full_name.split())
    if not re.fullmatch(r"[A-Za-z0-9_]{3,30}", username):
        return jsonify({"error": "Логин должен содержать 3–30 символов: латинские буквы, цифры или _"}), 400
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        return jsonify({"error": "Введите корректный адрес электронной почты"}), 400
    if full_name and (
        len(full_name) < 5 or len(full_name) > 100
        or not re.fullmatch(r"[A-Za-zА-Яа-яЁё -]+", full_name)
        or len(full_name.split()) < 2
    ):
        return jsonify({"error": "Укажите фамилию и имя буквами либо оставьте ФИО пустым"}), 400

    try:
        updated = db.update_user(user_id, username=username, email=email, full_name=full_name or None)
    except DuplicateKeyError:
        return jsonify({"error": "Такой логин или Email уже используется"}), 409
    if updated is None:
        return jsonify({"error": "Не удалось обновить профиль"}), 500

    session["username"] = updated["username"]
    return jsonify({
        "message": "Профиль успешно обновлён",
        "username": updated.get("username", ""),
        "full_name": updated.get("full_name") or "",
        "email": updated.get("email", ""),
    }), 200


@users_bp.route("/account-deletion-info", methods=["GET"])
def account_deletion_info():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Необходимо войти в аккаунт"}), 401

    owned = db.list_projects(owner_id=user_id)
    users = [
        {"_id": item["_id"], "username": item.get("username", "")}
        for item in db.list_users() if item.get("_id") != user_id
    ]
    return jsonify({
        "owned_projects": [
            {"_id": item["_id"], "name": item.get("name", "")}
            for item in owned
        ],
        "available_users": users,
    }), 200


@users_bp.route("/change-password", methods=["POST"])
def change_password():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Необходимо войти в аккаунт"}), 401

    data = request.get_json(silent=True) or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    if not isinstance(current_password, str) or not isinstance(new_password, str):
        return jsonify({"error": "Проверьте введённые данные"}), 400
    if len(new_password) < 8 or len(new_password) > 128:
        return jsonify({"error": "Новый пароль должен содержать от 8 до 128 символов"}), 400

    user = db.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return jsonify({"error": "Пользователь не найден. Войдите в аккаунт повторно."}), 404
    if not user.get("password_hash") or not check_password_hash(user["password_hash"], current_password):
        return jsonify({"error": "Текущий пароль указан неверно"}), 400

    db.update_user(user_id, password_hash=generate_password_hash(new_password))
    return jsonify({"message": "Пароль успешно изменён"}), 200


@users_bp.route("/delete-account", methods=["POST"])
def delete_current_account():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Необходимо войти в аккаунт"}), 401

    data = request.get_json(silent=True) or {}
    password = data.get("password", "")
    if not isinstance(password, str) or not password:
        return jsonify({"error": "Введите пароль для подтверждения"}), 400

    user = db.get_user_by_id(user_id)
    if user is None:
        session.clear()
        return jsonify({"error": "Пользователь не найден. Войдите в аккаунт повторно."}), 404
    if not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Неверный пароль"}), 400

    # Владение проектами должно быть передано заранее.
    owned_projects = db.list_projects(owner_id=user_id)
    if owned_projects:
        return jsonify({
            "error": "Сначала передайте владение всеми своими проектами другому участнику. После передачи можно удалить аккаунт.",
            "owned_projects": [{"_id": item["_id"], "name": item.get("name", "")} for item in owned_projects],
        }), 409

    # Задачи сохраняются. Помечаем удалённые связи, чтобы интерфейс
    # мог отличить удалённого автора/исполнителя от неназначенной роли.
    try:
        user_oid = ObjectId(user_id)
        collection = db.get_db().tasks
        collection.update_many(
            {"created_by_id": user_oid},
            {"$set": {"created_by_id": None, "created_by_deleted": True}}
        )
        collection.update_many(
            {"assignee_id": user_oid},
            {"$set": {"assignee_id": None, "assignee_deleted": True}}
        )
        if not db.delete_user(user_id):
            return jsonify({"error": "Не удалось удалить аккаунт. Обновите страницу и попробуйте снова."}), 500
    except Exception:
        return jsonify({"error": "Не удалось удалить аккаунт из-за ошибки базы данных"}), 500

    session.clear()
    return jsonify({"message": "Ваш аккаунт удалён"}), 200


@users_bp.route("/<user_id>", methods=["GET"])
def get_user(user_id):
    user = db.get_user_by_id(user_id)
    if user is None:
        return jsonify({"error": "Пользователь не найден"}), 404
    return jsonify(_public_user(user))


@users_bp.route("/", methods=["POST"])
def create_user():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    email = data.get("email")
    if not isinstance(username, str) or not username.strip():
        return jsonify({"error": "Укажите логин"}), 400
    if not isinstance(email, str) or not email.strip():
        return jsonify({"error": "Укажите Email"}), 400
    try:
        user = db.create_user(username.strip(), email.strip().lower(), "", data.get("full_name"))
    except DuplicateKeyError:
        return jsonify({"error": "Пользователь с таким логином или email уже существует"}), 409
    return jsonify(_public_user(user)), 201


@users_bp.route("/<user_id>", methods=["PATCH", "PUT"])
def update_user(user_id):
    data = request.get_json(silent=True) or {}
    data.pop("password_hash", None)
    try:
        user = db.update_user(user_id, **data)
    except DuplicateKeyError:
        return jsonify({"error": "Логин или email уже используется"}), 409
    if user is None:
        return jsonify({"error": "Пользователь не найден или указан неверный ID"}), 404
    return jsonify(_public_user(user))


@users_bp.route("/<user_id>", methods=["DELETE"])
def delete_user(user_id):
    if session.get("user_id") == user_id:
        return jsonify({"error": "Нельзя удалить текущую учётную запись"}), 400
    if not db.delete_user(user_id):
        return jsonify({"error": "Пользователь не найден или указан неверный ID"}), 404
    return "", 204
