from flask import Blueprint, jsonify, request, session
import db

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")
VALID_STATUSES = {"TODO", "IN_PROGRESS", "DONE"}


def _permissions(task):
    # Создатель задачи и владелец проекта могут полностью управлять задачей.
    user_id = session.get("user_id")
    is_creator = bool(user_id and task and task.get("created_by_id") == user_id)
    project = db.get_project_by_id(task.get("project_id")) if task else None
    is_project_owner = bool(
        user_id and project and project.get("owner_id") == user_id
    )
    can_manage = is_creator or is_project_owner
    return {
        "can_change_status": can_manage,
        "can_edit": can_manage,
        "can_delete": can_manage,
        "can_assign": can_manage,
    }


def _task_with_names(task):
    if not task:
        return task
    project = db.get_project_by_id(task.get("project_id"))
    creator = db.get_user_by_id(task.get("created_by_id")) if task.get("created_by_id") else None
    assignee = db.get_user_by_id(task.get("assignee_id")) if task.get("assignee_id") else None
    task["project_name"] = project.get("name") if project else "Проект не найден"
    task["creator_username"] = creator.get("username") if creator else "Автор не сохранён"
    task["assignee_username"] = assignee.get("username") if assignee else "Не назначен"
    task.update(_permissions(task))
    return task


def _get_task_or_404(task_id):
    task = db.get_task_by_id(task_id)
    if task is None:
        return None, (jsonify({"error": "Задача не найдена"}), 404)
    return task, None


@tasks_bp.route("/", methods=["GET"])
def list_tasks():
    tasks = db.list_tasks(
        request.args.get("project_id"),
        request.args.get("assignee_id"),
        request.args.get("status"),
    )
    return jsonify([_task_with_names(task) for task in tasks])


@tasks_bp.route("/stats", methods=["GET"])
def task_stats():
    tasks = db.list_tasks(project_id=request.args.get("project_id"))
    return jsonify({
        "total": len(tasks),
        "new": sum(1 for task in tasks if task.get("status") == "TODO"),
        "in_progress": sum(1 for task in tasks if task.get("status") == "IN_PROGRESS"),
        "done": sum(1 for task in tasks if task.get("status") == "DONE"),
    })


@tasks_bp.route("/", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    if not data.get("project_id") or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "Укажите проект и название задачи"}), 400
    status = data.get("status", "TODO")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Недопустимый статус задачи"}), 400
    if db.get_project_by_id(data["project_id"]) is None:
        return jsonify({"error": "Выбранный проект не найден"}), 404
    task = db.create_task(
        project_id=data["project_id"],
        title=data["title"].strip(),
        description=data.get("description"),
        assignee_id=data.get("assignee_id"),
        status=status,
        created_by_id=session.get("user_id"),
    )
    if task is None:
        return jsonify({"error": "Не удалось создать задачу"}), 400
    return jsonify(_task_with_names(task)), 201


@tasks_bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    return jsonify(_task_with_names(task))


@tasks_bp.route("/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    if not _permissions(task)["can_edit"]:
        return jsonify({"error": "Редактировать задачу может только её создатель"}), 403
    data = request.get_json(silent=True) or {}
    if "status" in data:
        return jsonify({"error": "Статус изменяется отдельной кнопкой"}), 400
    data.pop("created_by_id", None)
    data.pop("project_id", None)
    updated = db.update_task(task_id, **data)
    if updated is None:
        return jsonify({"error": "Не удалось обновить задачу"}), 404
    return jsonify(_task_with_names(updated))


@tasks_bp.route("/<task_id>/assign", methods=["PATCH"])
def assign_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    if not _permissions(task)["can_assign"]:
        return jsonify({"error": "Назначать участника может только создатель задачи"}), 403
    data = request.get_json(silent=True) or {}
    assignee_id = data.get("assignee_id")
    if assignee_id and db.get_user_by_id(assignee_id) is None:
        return jsonify({"error": "Исполнитель не найден"}), 404
    updated = db.assign_task(task_id, assignee_id)
    return jsonify(_task_with_names(updated))


@tasks_bp.route("/<task_id>/move", methods=["PATCH"])
def move_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    if not _permissions(task)["can_change_status"]:
        return jsonify({"error": "Изменять статус может только создатель задачи"}), 403
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in VALID_STATUSES:
        return jsonify({"error": "Выбран недопустимый статус"}), 400
    updated = db.move_task(task_id, new_status=status, new_position=data.get("position"))
    if updated is None:
        return jsonify({"error": "Не удалось изменить статус задачи"}), 404
    return jsonify(_task_with_names(updated))


@tasks_bp.route("/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    task, error = _get_task_or_404(task_id)
    if error:
        return error
    if not _permissions(task)["can_delete"]:
        return jsonify({"error": "Удалить задачу может только её создатель"}), 403
    if not db.delete_task(task_id):
        return jsonify({"error": "Не удалось удалить задачу"}), 404
    return "", 204
