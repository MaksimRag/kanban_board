from flask import Blueprint, jsonify, request, session
import db

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")
VALID_STATUSES = {"TODO", "IN_PROGRESS", "DONE"}


def _project_for_task(task):
    return db.get_project_by_id(task.get("project_id")) if task else None


def _can_access(task):
    return bool(task and db.is_project_member(task.get("project_id"), session.get("user_id")))


def _permissions(task):
    project = _project_for_task(task)
    user_id = session.get("user_id")
    is_owner = bool(project and project.get("owner_id") == user_id)
    is_member = _can_access(task)
    is_creator = bool(task and task.get("created_by_id") == user_id)
    can_edit = is_member
    return {
        "can_change_status": is_member,
        "can_edit": can_edit,
        "can_delete": bool(is_owner or is_creator),
        "can_assign": is_member,
        "can_view": is_member,
    }


def _task_with_names(task):
    if not task:
        return task
    project = _project_for_task(task)
    creator = db.get_user_by_id(task.get("created_by_id")) if task.get("created_by_id") else None
    assignee = db.get_user_by_id(task.get("assignee_id")) if task.get("assignee_id") else None
    task["project_name"] = project.get("name") if project else "Проект не найден"
    task["creator_username"] = creator.get("username") if creator else ("Удалённый пользователь" if task.get("created_by_deleted") else "Автор не сохранён")
    task["assignee_username"] = assignee.get("username") if assignee else (
        "Удалённый пользователь" if task.get("assignee_deleted")
        else ("Не назначен (участник покинул проект)" if task.get("assignee_unassigned") else "Не назначен")
    )
    task.update(_permissions(task))
    return task


def _get_task_or_404(task_id):
    task = db.get_task_by_id(task_id)
    if task is None:
        return None, (jsonify({"error": "Задача не найдена"}), 404)
    if not _can_access(task):
        return None, (jsonify({"error": "Нет доступа к задачам этого проекта"}), 403)
    return task, None


@tasks_bp.route("/", methods=["GET"])
def list_tasks():
    visible_projects = db.list_accessible_projects(session.get("user_id"))
    visible_ids = {p["_id"] for p in visible_projects}
    project_id = request.args.get("project_id")
    if project_id and project_id not in visible_ids:
        return jsonify({"error": "Нет доступа к выбранному проекту"}), 403
    tasks = db.list_tasks(project_id=project_id, assignee_id=request.args.get("assignee_id"), status=request.args.get("status")) if project_id else [
        task for pid in visible_ids for task in db.list_tasks(project_id=pid)
    ]
    return jsonify([_task_with_names(task) for task in tasks])


@tasks_bp.route("/stats", methods=["GET"])
def task_stats():
    project_id = request.args.get("project_id")
    if project_id and not db.is_project_member(project_id, session.get("user_id")):
        return jsonify({"error": "Нет доступа к выбранному проекту"}), 403
    visible_ids = [project_id] if project_id else [p["_id"] for p in db.list_accessible_projects(session.get("user_id"))]
    tasks = [task for pid in visible_ids for task in db.list_tasks(project_id=pid)]
    return jsonify({"total": len(tasks), "new": sum(t.get("status") == "TODO" for t in tasks),
                    "in_progress": sum(t.get("status") == "IN_PROGRESS" for t in tasks),
                    "done": sum(t.get("status") == "DONE" for t in tasks)})


@tasks_bp.route("/", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")
    title = data.get("title")
    if not project_id or not isinstance(title, str) or not title.strip():
        return jsonify({"error": "Укажите проект и название задачи"}), 400
    if not db.is_project_member(project_id, session.get("user_id")):
        return jsonify({"error": "Создавать задачи могут только участники проекта"}), 403
    status = data.get("status", "TODO")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Недопустимый статус задачи"}), 400
    assignee_id = data.get("assignee_id")
    if assignee_id and not db.is_project_member(project_id, assignee_id):
        return jsonify({"error": "Исполнитель должен состоять в выбранном проекте"}), 400
    task = db.create_task(project_id, title.strip(), data.get("description"), assignee_id, status, session.get("user_id"))
    if not task:
        return jsonify({"error": "Не удалось создать задачу"}), 400
    return jsonify(_task_with_names(task)), 201


@tasks_bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    task, error = _get_task_or_404(task_id)
    return error or jsonify(_task_with_names(task))


@tasks_bp.route("/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    if "status" in data:
        return jsonify({"error": "Статус изменяется отдельным действием"}), 400
    if "assignee_id" in data and data["assignee_id"] and not db.is_project_member(task["project_id"], data["assignee_id"]):
        return jsonify({"error": "Исполнитель должен состоять в выбранном проекте"}), 400
    allowed = {key: data[key] for key in ("title", "description", "assignee_id") if key in data}
    if "title" in allowed and (not isinstance(allowed["title"], str) or not allowed["title"].strip()):
        return jsonify({"error": "Название задачи не может быть пустым"}), 400
    if "title" in allowed:
        allowed["title"] = allowed["title"].strip()
    updated = db.update_task(task_id, **allowed)
    return jsonify(_task_with_names(updated))


@tasks_bp.route("/<task_id>/assign", methods=["PATCH"])
def assign_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    if assignee_id and not db.is_project_member(task["project_id"], assignee_id):
        return jsonify({"error": "Исполнитель должен состоять в проекте"}), 400
    return jsonify(_task_with_names(db.assign_task(task_id, assignee_id)))


@tasks_bp.route("/<task_id>/move", methods=["PATCH"])
def move_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Выбран недопустимый статус"}), 400
    updated = db.move_task(task_id, status, data.get("position"))
    return jsonify(_task_with_names(updated))


@tasks_bp.route("/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    permissions = _permissions(task)
    if not permissions["can_delete"]:
        return jsonify({"error": "Удалить задачу может её создатель или владелец проекта"}), 403
    return ("", 204) if db.delete_task(task_id) else (jsonify({"error": "Не удалось удалить задачу"}), 404)
