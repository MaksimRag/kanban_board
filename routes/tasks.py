from flask import Blueprint, jsonify, request
import db

tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")


@tasks_bp.route("/", methods=["GET"])
def list_tasks():
    project_id = request.args.get("project_id")
    assignee_id = request.args.get("assignee_id")
    status = request.args.get("status")
    return jsonify(db.list_tasks(project_id, assignee_id, status))


@tasks_bp.route("/", methods=["POST"])
def create_task():
    data = request.get_json() or {}
    task = db.create_task(
        project_id=data.get("project_id"),
        title=data.get("title"),
        description=data.get("description"),
        assignee_id=data.get("assignee_id"),
        status=data.get("status", "TODO"),
    )
    if task is None:
        return {"error": "Invalid project_id"}, 400
    return jsonify(task), 201


@tasks_bp.route("/<task_id>", methods=["PATCH"])
def update_task(task_id):
    data = request.get_json() or {}
    task = db.update_task(task_id, **data)
    if task is None:
        return {"error": "Task not found"}, 404
    return jsonify(task)


@tasks_bp.route("/<task_id>/assign", methods=["PATCH"])
def assign_task(task_id):
    data = request.get_json() or {}
    task = db.assign_task(task_id, data.get("assignee_id"))
    if task is None:
        return {"error": "Task not found"}, 404
    return jsonify(task)


@tasks_bp.route("/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    if not db.delete_task(task_id):
        return {"error": "Task not found"}, 404
    return "", 204