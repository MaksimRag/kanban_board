from flask import Blueprint, jsonify, request
import db

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("/", methods=["GET"])
def list_tasks():
    project_id = request.args.get("project_id")
    assignee_id = request.args.get("assignee_id")
    status = request.args.get("status")
    return jsonify(db.list_tasks(project_id, assignee_id, status))


@tasks_bp.route("/stats", methods=["GET"])
def task_stats():
    project_id = request.args.get("project_id")
    tasks = db.list_tasks(project_id=project_id)
    return jsonify({
        "total": len(tasks),
        "new": sum(1 for task in tasks if task.get("status") in ("TODO", "Новая")),
        "in_progress": sum(1 for task in tasks if task.get("status") in ("IN_PROGRESS", "В работе")),
        "done": sum(1 for task in tasks if task.get("status") in ("DONE", "Выполнена")),
    })


@tasks_bp.route("/", methods=["POST"])
def create_task():
    data = request.get_json(silent=True) or {}
    if not data.get("project_id") or not isinstance(data.get("title"), str) or not data["title"].strip():
        return jsonify({"error": "Fields 'project_id' and 'title' are required"}), 400

    task = db.create_task(
        project_id=data["project_id"],
        title=data["title"].strip(),
        description=data.get("description"),
        assignee_id=data.get("assignee_id"),
        status=data.get("status", "TODO"),
    )
    if task is None:
        return jsonify({"error": "Invalid project_id"}), 400
    return jsonify(task), 201


@tasks_bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    task = db.get_task_by_id(task_id)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@tasks_bp.route("/<task_id>", methods=["PATCH", "PUT"])
def update_task(task_id):
    data = request.get_json(silent=True) or {}
    task = db.update_task(task_id, **data)
    if task is None:
        return jsonify({"error": "Task not found or invalid id"}), 404
    return jsonify(task)


@tasks_bp.route("/<task_id>/assign", methods=["PATCH"])
def assign_task(task_id):
    data = request.get_json(silent=True) or {}
    task = db.assign_task(task_id, data.get("assignee_id"))
    if task is None:
        return jsonify({"error": "Task not found or invalid id"}), 404
    return jsonify(task)


@tasks_bp.route("/<task_id>/move", methods=["PATCH"])
def move_task(task_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if not status:
        return jsonify({"error": "Field 'status' is required"}), 400
    task = db.move_task(task_id, new_status=status, new_position=data.get("position"))
    if task is None:
        return jsonify({"error": "Task not found or invalid id"}), 404
    return jsonify(task)


@tasks_bp.route("/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    if not db.delete_task(task_id):
        return jsonify({"error": "Task not found or invalid id"}), 404
    return "", 204