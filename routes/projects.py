from flask import Blueprint, jsonify, request
import db

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


@projects_bp.route("/", methods=["GET"])
def list_projects():
    """
    GET /projects
    GET /projects?owner_id=<user_id>  — только проекты конкретного владельца
    """
    owner_id = request.args.get("owner_id")
    return jsonify(db.list_projects(owner_id=owner_id))


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    project = db.get_project_by_id(project_id)
    if project is None:
        return {"error": "Project not found"}, 404
    return jsonify(project)


@projects_bp.route("/", methods=["POST"])
def create_project():
    """
    POST /projects
    Body: { "name": "...", "owner_id": "<user_id>", "description": "..." }
    """
    data = request.get_json() or {}

    name = data.get("name")
    owner_id = data.get("owner_id")

    if not name or not owner_id:
        return {"error": "Fields 'name' and 'owner_id' are required"}, 400

    project = db.create_project(
        name=name,
        owner_id=owner_id,
        description=data.get("description"),
    )
    if project is None:
        return {"error": "Invalid owner_id"}, 400

    return jsonify(project), 201