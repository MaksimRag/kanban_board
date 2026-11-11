from flask import Blueprint, jsonify, request
from pymongo.errors import DuplicateKeyError
import db

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/", methods=["GET"])
def list_projects():
    owner_id = request.args.get("owner_id")
    return jsonify(db.list_projects(owner_id=owner_id))


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    project = db.get_project_by_id(project_id)
    if project is None:
        return jsonify({"error": "Project not found"}), 404
    return jsonify(project)


@projects_bp.route("/", methods=["POST"])
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    owner_id = data.get("owner_id")

    if not isinstance(name, str) or not name.strip() or not owner_id:
        return jsonify({"error": "Fields 'name' and 'owner_id' are required"}), 400

    project = db.create_project(
        name=name.strip(),
        owner_id=owner_id,
        description=data.get("description"),
    )
    if project is None:
        return jsonify({"error": "Invalid owner_id"}), 400
    return jsonify(project), 201


@projects_bp.route("/<project_id>", methods=["PATCH", "PUT"])
def update_project(project_id):
    data = request.get_json(silent=True) or {}
    project = db.update_project(project_id, **data)
    if project is None:
        return jsonify({"error": "Project not found or invalid id"}), 404
    return jsonify(project)


@projects_bp.route("/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    if not db.delete_project(project_id):
        return jsonify({"error": "Project not found or invalid id"}), 404
    return "", 204