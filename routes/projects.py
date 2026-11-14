from flask import Blueprint, jsonify, request, session
import db

projects_bp = Blueprint("projects", __name__, url_prefix="/projects")


def _is_owner(project):
    return bool(project and project.get("owner_id") == session.get("user_id"))


def _require_member(project_id):
    if not db.is_project_member(project_id, session.get("user_id")):
        return jsonify({"error": "У вас нет доступа к этому проекту. Сначала примите приглашение."}), 403
    return None


def _project_with_owner(project):
    if not project:
        return project
    owner = db.get_user_by_id(project.get("owner_id")) if project.get("owner_id") else None
    project["owner_username"] = owner.get("username") if owner else "Неизвестный пользователь"
    project["can_manage"] = _is_owner(project)
    project["is_member"] = db.is_project_member(project["_id"], session.get("user_id"))
    return project


@projects_bp.route("/discoverable", methods=["GET"])
def discoverable_projects():
    return jsonify(db.list_discoverable_projects(session.get("user_id")))


@projects_bp.route("/join-requests", methods=["GET"])
def incoming_join_requests():
    return jsonify(db.list_join_requests_for_owner(session.get("user_id")))


@projects_bp.route("/<project_id>/join-requests", methods=["POST"])
def request_to_join_project(project_id):
    result, error = db.create_project_join_request(project_id, session.get("user_id"))
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Заявка отправлена владельцу проекта", "request": result}), 201


@projects_bp.route("/join-requests/<request_id>/respond", methods=["POST"])
def respond_to_join_request(request_id):
    data = request.get_json(silent=True) or {}
    accept = data.get("accept")
    if not isinstance(accept, bool):
        return jsonify({"error": "Укажите, принять или отклонить заявку"}), 400
    result, error = db.respond_project_join_request(request_id, session.get("user_id"), accept)
    if error:
        return jsonify({"error": error}), 403
    return jsonify({"message": "Участник добавлен в проект" if accept else "Заявка отклонена"})


@projects_bp.route("/", methods=["GET"])
def list_projects():
    return jsonify([_project_with_owner(p) for p in db.list_accessible_projects(session.get("user_id"))])


@projects_bp.route("/<project_id>", methods=["GET"])
def get_project(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    denied = _require_member(project_id)
    if denied:
        return denied
    return jsonify(_project_with_owner(project))


@projects_bp.route("/", methods=["POST"])
def create_project():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return jsonify({"error": "Укажите название проекта"}), 400
    project = db.create_project(name.strip(), session.get("user_id"), data.get("description"))
    if not project:
        return jsonify({"error": "Не удалось создать проект"}), 400
    return jsonify(_project_with_owner(project)), 201


@projects_bp.route("/<project_id>", methods=["PATCH", "PUT"])
def update_project(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Редактировать проект может только его владелец"}), 403
    data = request.get_json(silent=True) or {}
    if "name" in data and (not isinstance(data["name"], str) or not data["name"].strip()):
        return jsonify({"error": "Название проекта не может быть пустым"}), 400
    updated = db.update_project(project_id, name=data.get("name", project.get("name")), description=data.get("description", project.get("description")))
    return jsonify(_project_with_owner(updated))


@projects_bp.route("/<project_id>", methods=["DELETE"])
def delete_project(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Удалить проект может только его владелец"}), 403
    return ("", 204) if db.delete_project(project_id) else (jsonify({"error": "Не удалось удалить проект"}), 500)


@projects_bp.route("/<project_id>/members", methods=["GET"])
def project_members(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    denied = _require_member(project_id)
    if denied:
        return denied
    return jsonify({
        "members": db.list_project_members(project_id),
        "can_manage": _is_owner(project),
        "project": {"_id": project["_id"], "name": project.get("name", "")}
    })


@projects_bp.route("/<project_id>/invite-candidates", methods=["GET"])
def invite_candidates(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Приглашать участников может только владелец проекта"}), 403
    return jsonify(db.list_project_invite_candidates(project_id))


@projects_bp.route("/<project_id>/invitations", methods=["GET"])
def list_project_invitations(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Просматривать отправленные приглашения может только владелец"}), 403
    return jsonify(db.list_project_invitations(project_id))


@projects_bp.route("/<project_id>/invitations/<invitation_id>", methods=["DELETE"])
def cancel_project_invitation(project_id, invitation_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Отменять приглашения может только владелец"}), 403
    if not db.cancel_project_invitation(project_id, invitation_id):
        return jsonify({"error": "Ожидающее приглашение не найдено"}), 404
    return "", 204


@projects_bp.route("/<project_id>/invitations", methods=["POST"])
def invite_member(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Приглашать участников может только владелец проекта"}), 403
    data = request.get_json(silent=True) or {}
    invitee_id = data.get("user_id")
    invitation, error = db.add_project_invitation(project_id, session.get("user_id"), invitee_id)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"message": "Приглашение отправлено", "invitation": invitation}), 201


@projects_bp.route("/invitations", methods=["GET"])
def my_invitations():
    return jsonify(db.list_invitations_for_user(session.get("user_id")))


@projects_bp.route("/invitations/<invitation_id>/respond", methods=["POST"])
def respond_invitation(invitation_id):
    data = request.get_json(silent=True) or {}
    accept = data.get("accept")
    if not isinstance(accept, bool):
        return jsonify({"error": "Укажите, принять или отклонить приглашение"}), 400
    invitation, error = db.respond_project_invitation(invitation_id, session.get("user_id"), accept)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"message": "Вы вступили в проект" if accept else "Приглашение отклонено"})


@projects_bp.route("/<project_id>/members/<user_id>", methods=["DELETE"])
def remove_member(project_id, user_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Управлять составом проекта может только владелец"}), 403
    if user_id == project.get("owner_id"):
        return jsonify({"error": "Нельзя исключить владельца проекта"}), 400
    if not db.remove_project_member(project_id, user_id):
        return jsonify({"error": "Участник не найден в этом проекте"}), 404
    return "", 204


@projects_bp.route("/<project_id>/leave", methods=["POST"])
def leave_project(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if _is_owner(project):
        return jsonify({"error": "Владелец не может покинуть проект. Сначала передайте владение."}), 409
    if not db.remove_project_member(project_id, session.get("user_id")):
        return jsonify({"error": "Вы не состоите в этом проекте"}), 404
    member = db.get_user_by_id(session.get("user_id"))
    db.create_notification(
        project.get("owner_id"), "member_left", "Участник покинул проект",
        f"Пользователь @{(member or {}).get('username', 'участник')} покинул проект «{project.get('name', '')}».",
        project_id
    )
    return jsonify({"message": "Вы покинули проект"})


@projects_bp.route("/<project_id>/transfer-owner", methods=["POST"])
def transfer_project_owner(project_id):
    project = db.get_project_by_id(project_id)
    if not project:
        return jsonify({"error": "Проект не найден"}), 404
    if not _is_owner(project):
        return jsonify({"error": "Передать владение может только текущий владелец"}), 403
    data = request.get_json(silent=True) or {}
    new_owner_id = data.get("new_owner_id")
    if not new_owner_id or not db.is_project_member(project_id, new_owner_id):
        return jsonify({"error": "Новым владельцем может стать только принятый участник проекта"}), 400
    updated = db.transfer_project_owner(project_id, new_owner_id)
    if not updated:
        return jsonify({"error": "Не удалось передать владение"}), 500
    return jsonify({"message": "Владение проектом передано", "project": _project_with_owner(updated)})
