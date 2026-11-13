from flask import Blueprint, jsonify, request, session
import db

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


def _project_with_owner(project):
    if not project:
        return project
    owner = db.get_user_by_id(project.get("owner_id")) if project.get("owner_id") else None
    # В интерфейсе показываем только логин владельца, не его внутренний ID.
    project["owner_username"] = owner.get("username") if owner else "Неизвестный пользователь"
    project["can_manage"] = bool(
        session.get("user_id") and project.get("owner_id") == session.get("user_id")
    )
    return project


def _owner_required(project):
    if project.get("owner_id") != session.get("user_id"):
        return jsonify({"error": "Управлять проектом может только его создатель"}), 403
    return None


@projects_bp.route("/", methods=["GET"])
def list_projects():
    owner_id = request.args.get("owner_id")
    return jsonify([_project_with_owner(project) for project in db.list_projects(owner_id=owner_id)])


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    project = db.get_project_by_id(project_id)
    if project is None:
        return jsonify({"error": "Проект не найден"}), 404
    return jsonify(_project_with_owner(project))


@projects_bp.route("/", methods=["POST"])
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Укажите название проекта"}), 400
    # Владелец определяется сервером по текущей сессии.
    project = db.create_project(
        name=name.strip(),
        owner_id=session.get("user_id"),
        description=data.get("description"),
    )
    if project is None:
        return jsonify({"error": "Не удалось создать проект"}), 400
    return jsonify(_project_with_owner(project)), 201


@projects_bp.route("/<project_id>", methods=["PATCH", "PUT"])
def update_project(project_id):
    project = db.get_project_by_id(project_id)
    if project is None:
        return jsonify({"error": "Проект не найден"}), 404
    denied = _owner_required(project)
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    data.pop("owner_id", None)
    updated = db.update_project(project_id, **data)
    return jsonify(_project_with_owner(updated))


@projects_bp.route("/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    project = db.get_project_by_id(project_id)
    if project is None:
        return jsonify({"error": "Проект не найден"}), 404
    denied = _owner_required(project)
    if denied:
        return denied
    if not db.delete_project(project_id):
        return jsonify({"error": "Не удалось удалить проект"}), 404
    return "", 204
