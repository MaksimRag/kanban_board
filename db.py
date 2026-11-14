import certifi
from flask_pymongo import PyMongo
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
from pymongo.errors import CollectionInvalid
from config import settings

mongo = PyMongo()


# ============================================================
# Инициализация
# ============================================================

def create_notification(user_id, notification_type, title, message, project_id=None):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return None
    project_oid = _parse_id(project_id) if project_id else None
    doc = {
        "user_id": user_oid,
        "type": notification_type,
        "title": title,
        "message": message,
        "project_id": project_oid,
        "is_read": False,
        "created_at": datetime.utcnow(),
    }
    result = get_db().notifications.insert_one(doc)
    doc["_id"] = result.inserted_id
    doc["_id"] = str(doc["_id"])
    doc["user_id"] = str(doc["user_id"])
    doc["project_id"] = str(doc["project_id"]) if doc.get("project_id") else None
    return doc


def list_notifications(user_id, limit=100):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return []
    rows = get_db().notifications.find({"user_id": user_oid}).sort("created_at", -1).limit(limit)
    result = []
    for row in rows:
        item = _to_str(row)
        item["user_id"] = str(row["user_id"])
        item["project_id"] = str(row["project_id"]) if row.get("project_id") else None
        created_at = row.get("created_at")
        if hasattr(created_at, "isoformat"):
            # MongoDB stores notification timestamps in UTC. Mark the value explicitly
            # so browsers do not mistake a naive UTC timestamp for local time.
            if created_at.tzinfo is not None:
                from datetime import timezone
                created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
            item["created_at"] = created_at.isoformat(timespec="milliseconds") + "Z"
        else:
            item["created_at"] = None
        result.append(item)
    return result


def mark_notification_read(notification_id, user_id):
    notification_oid, user_oid = _parse_id(notification_id), _parse_id(user_id)
    if notification_oid is None or user_oid is None:
        return False
    result = get_db().notifications.update_one(
        {"_id": notification_oid, "user_id": user_oid},
        {"$set": {"is_read": True}}
    )
    return result.matched_count == 1


def mark_all_notifications_read(user_id):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return 0
    result = get_db().notifications.update_many(
        {"user_id": user_oid, "is_read": False},
        {"$set": {"is_read": True}}
    )
    return result.modified_count


def delete_all_notifications(user_id):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return 0
    result = get_db().notifications.delete_many({"user_id": user_oid})
    return result.deleted_count


def init_db(app):
    app.config["MONGO_URI"] = settings.MONGODB_URI
    mongo.init_app(app, tlsCAFile=certifi.where())

    with app.app_context():
        try:
            mongo.cx.admin.command("ping")
            print("✅ MongoDB Atlas connected")
            print(f"📂 База данных: {settings.DB_NAME}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise

        init_collections()


def init_collections():
    """
    Явно создаёт коллекции (если их нет) и индексы.
    В MongoDB коллекции создаются и автоматически при первой вставке,
    но явное создание полезно для контроля и создания индексов на старте.
    """
    db = get_db()

    # Явное создание коллекций (если не существуют)
    for name in ["users", "projects", "tasks", "project_memberships", "project_invitations", "project_join_requests", "notifications"]:
        try:
            db.create_collection(name)
            print(f"📁 Коллекция '{name}' создана")
        except CollectionInvalid:
            # Коллекция уже существует — это нормально
            pass

    # Индексы (идемпотентны — можно вызывать повторно)
    db.users.create_index("email", unique=True)
    db.users.create_index("username", unique=True)
    db.projects.create_index("owner_id")
    db.project_memberships.create_index([("project_id", 1), ("user_id", 1)], unique=True)
    db.project_invitations.create_index([("project_id", 1), ("invitee_id", 1), ("status", 1)])
    db.project_invitations.create_index([("invitee_id", 1), ("status", 1)])
    db.project_join_requests.create_index([("project_id", 1), ("user_id", 1), ("status", 1)])
    db.project_join_requests.create_index([("user_id", 1), ("status", 1)])
    db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    db.notifications.create_index([("user_id", 1), ("is_read", 1)])
    db.tasks.create_index("project_id")
    db.tasks.create_index("assignee_id")
    db.tasks.create_index([("project_id", 1), ("status", 1), ("position", 1)])
    print("📇 Индексы проверены/созданы")


def get_db():
    return mongo.cx[settings.DB_NAME]


# ============================================================
# Вспомогательные функции
# ============================================================

def _to_str(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def _parse_id(id_str):
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None


def _task_to_dict(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    doc["project_id"] = str(doc["project_id"])
    doc["assignee_id"] = str(doc["assignee_id"]) if doc.get("assignee_id") else None
    doc["created_by_id"] = str(doc["created_by_id"]) if doc.get("created_by_id") else None
    for date_field in ("created_at", "updated_at"):
        value = doc.get(date_field)
        if hasattr(value, "isoformat"):
            doc[date_field] = value.isoformat()
    return doc


def _project_to_dict(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    doc["owner_id"] = str(doc["owner_id"])
    return doc


# ============================================================
# USERS
# ============================================================

def create_user(username, email, password_hash, full_name=None):
    db = get_db()
    doc = {
        "username": username,
        "email": email,
        "password_hash": password_hash,
        "full_name": full_name,
        "created_at": datetime.utcnow(),
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _to_str(doc)


def get_user_by_id(user_id):
    oid = _parse_id(user_id)
    if oid is None:
        return None
    return _to_str(get_db().users.find_one({"_id": oid}))


def get_user_by_email(email):
    return _to_str(get_db().users.find_one({"email": email}))


def get_user_by_username(username):
    return _to_str(get_db().users.find_one({"username": username}))


def list_users():
    return [_to_str(u) for u in get_db().users.find()]


def update_user(user_id, **fields):
    """Обновляет разрешённые поля пользователя."""
    oid = _parse_id(user_id)
    if oid is None:
        return None

    allowed = {"username", "email", "password_hash", "full_name"}
    update = {k: v for k, v in fields.items() if k in allowed}
    if not update:
        return get_user_by_id(user_id)

    get_db().users.update_one({"_id": oid}, {"$set": update})
    return get_user_by_id(user_id)


def delete_user(user_id):
    oid = _parse_id(user_id)
    if oid is None:
        return False
    database = get_db()
    database.project_memberships.delete_many({"user_id": oid})
    database.project_invitations.delete_many({"$or": [{"invitee_id": oid}, {"inviter_id": oid}]})
    database.tasks.update_many({"assignee_id": oid}, {"$set": {"assignee_id": None, "assignee_unassigned": True}})
    database.tasks.update_many({"created_by_id": oid}, {"$set": {"created_by_id": None, "created_by_deleted": True}})
    result = database.users.delete_one({"_id": oid})
    return result.deleted_count == 1


# ============================================================
# PROJECTS
# ============================================================

def create_project(name, owner_id, description=None):
    owner_oid = _parse_id(owner_id)
    if owner_oid is None:
        return None
    db = get_db()
    doc = {
        "name": name,
        "description": description,
        "owner_id": owner_oid,
        "created_at": datetime.utcnow(),
    }
    result = db.projects.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _project_to_dict(doc)


def get_project_by_id(project_id):
    oid = _parse_id(project_id)
    if oid is None:
        return None
    return _project_to_dict(get_db().projects.find_one({"_id": oid}))


def list_projects(owner_id=None):
    query = {}
    if owner_id:
        oid = _parse_id(owner_id)
        if oid is None:
            return []
        query["owner_id"] = oid
    return [_project_to_dict(d) for d in get_db().projects.find(query)]


def update_project(project_id, **fields):
    """Обновляет разрешённые поля проекта."""
    oid = _parse_id(project_id)
    if oid is None:
        return None

    allowed = {"name", "description"}
    update = {k: v for k, v in fields.items() if k in allowed}
    if not update:
        return get_project_by_id(project_id)

    get_db().projects.update_one({"_id": oid}, {"$set": update})
    return get_project_by_id(project_id)


def transfer_project_owner(project_id, new_owner_id):
    """Передаёт владение проектом существующему пользователю."""
    project_oid = _parse_id(project_id)
    owner_oid = _parse_id(new_owner_id)
    if project_oid is None or owner_oid is None:
        return None
    database = get_db()
    if database.users.find_one({"_id": owner_oid}) is None:
        return None
    current = database.projects.find_one({"_id": project_oid}, {"owner_id": 1})
    if not current:
        return None
    previous_owner = current.get("owner_id")
    result = database.projects.update_one(
        {"_id": project_oid},
        {"$set": {"owner_id": owner_oid}}
    )
    if result.matched_count:
        if previous_owner and previous_owner != owner_oid:
            database.project_memberships.update_one(
                {"project_id": project_oid, "user_id": previous_owner},
                {"$set": {"status": "accepted", "joined_at": datetime.utcnow()},
                 "$setOnInsert": {"created_at": datetime.utcnow()}},
                upsert=True
            )
        database.project_memberships.delete_one({"project_id": project_oid, "user_id": owner_oid})
        return get_project_by_id(project_id)
    return None


def delete_project(project_id):
    """Удаляет проект и все его задачи (каскадное удаление)."""
    oid = _parse_id(project_id)
    if oid is None:
        return False

    db = get_db()
    # Сначала удаляем задачи проекта
    db.tasks.delete_many({"project_id": oid})
    # Удаляем членство и приглашения, связанные с проектом
    db.project_memberships.delete_many({"project_id": oid})
    db.project_invitations.delete_many({"project_id": oid})
    # Затем сам проект
    result = db.projects.delete_one({"_id": oid})
    return result.deleted_count == 1


# ============================================================
# PROJECT MEMBERSHIPS AND INVITATIONS
# ============================================================

def is_project_member(project_id, user_id):
    project_oid, user_oid = _parse_id(project_id), _parse_id(user_id)
    if project_oid is None or user_oid is None:
        return False
    project = get_db().projects.find_one({"_id": project_oid, "owner_id": user_oid}, {"_id": 1})
    if project:
        return True
    return get_db().project_memberships.find_one(
        {"project_id": project_oid, "user_id": user_oid, "status": "accepted"},
        {"_id": 1}
    ) is not None


def list_accessible_projects(user_id):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return []
    db = get_db()
    project_ids = [row["project_id"] for row in db.project_memberships.find(
        {"user_id": user_oid, "status": "accepted"}, {"project_id": 1}
    )]
    query = {"$or": [{"owner_id": user_oid}, {"_id": {"$in": project_ids}}]}
    return [_project_to_dict(row) for row in db.projects.find(query)]


def list_discoverable_projects(user_id):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return []
    database = get_db()
    memberships = [row["project_id"] for row in database.project_memberships.find(
        {"user_id": user_oid, "status": "accepted"}, {"project_id": 1}
    )]
    pending = [row["project_id"] for row in database.project_join_requests.find(
        {"user_id": user_oid, "status": "pending"}, {"project_id": 1}
    )]
    excluded = list(set(memberships + pending))
    rows = database.projects.find({"owner_id": {"$ne": user_oid}, "_id": {"$nin": excluded}})
    result = []
    for row in rows:
        item = _project_to_dict(row)
        owner = get_user_by_id(item.get("owner_id"))
        item["owner_username"] = owner.get("username") if owner else "Неизвестный пользователь"
        item["member_count"] = len(list_project_members(item["_id"]))
        result.append(item)
    return result


def create_project_join_request(project_id, user_id):
    project_oid, user_oid = _parse_id(project_id), _parse_id(user_id)
    if project_oid is None or user_oid is None:
        return None, "Некорректные данные"
    database = get_db()
    project = database.projects.find_one({"_id": project_oid})
    if not project:
        return None, "Проект не найден"
    if is_project_member(project_id, user_id):
        return None, "Вы уже состоите в этом проекте"
    pending_invite = database.project_invitations.find_one({
        "project_id": project_oid, "invitee_id": user_oid, "status": "pending"
    })
    if pending_invite:
        return None, "У вас уже есть приглашение в этот проект. Проверьте входящие приглашения."
    existing = database.project_join_requests.find_one({
        "project_id": project_oid, "user_id": user_oid, "status": "pending"
    })
    if existing:
        return None, "Заявка уже отправлена и ожидает рассмотрения"
    doc = {"project_id": project_oid, "user_id": user_oid, "status": "pending",
           "created_at": datetime.utcnow()}
    result = database.project_join_requests.insert_one(doc)
    doc["_id"] = result.inserted_id
    applicant = get_user_by_id(user_id)
    create_notification(
        project.get("owner_id"), "join_request", "Новая заявка на вступление",
        f"Пользователь @{(applicant or {}).get('username', 'участник')} хочет вступить в проект «{project.get('name', '')}».",
        project_id
    )
    return _to_str(doc), None


def list_join_requests_for_owner(owner_id):
    owner_oid = _parse_id(owner_id)
    if owner_oid is None:
        return []
    database = get_db()
    owned = list(database.projects.find({"owner_id": owner_oid}, {"_id": 1, "name": 1}))
    project_map = {row["_id"]: row for row in owned}
    rows = database.project_join_requests.find({
        "project_id": {"$in": list(project_map)}, "status": "pending"
    }).sort("created_at", -1)
    result = []
    for row in rows:
        item = _to_str(row)
        project = project_map.get(row["project_id"], {})
        user = get_user_by_id(item.get("user_id"))
        item["project_name"] = project.get("name", "")
        item["username"] = user.get("username") if user else "Удалённый пользователь"
        item["full_name"] = user.get("full_name") if user else ""
        item["email"] = user.get("email") if user else ""
        result.append(item)
    return result


def respond_project_join_request(request_id, owner_id, accept):
    request_oid, owner_oid = _parse_id(request_id), _parse_id(owner_id)
    if request_oid is None or owner_oid is None:
        return None, "Заявка не найдена"
    database = get_db()
    row = database.project_join_requests.find_one({"_id": request_oid, "status": "pending"})
    if not row:
        return None, "Заявка не найдена или уже обработана"
    project = database.projects.find_one({"_id": row["project_id"], "owner_id": owner_oid})
    if not project:
        return None, "Рассматривать заявку может только владелец проекта"
    status = "accepted" if accept else "rejected"
    database.project_join_requests.update_one(
        {"_id": request_oid, "status": "pending"},
        {"$set": {"status": status, "responded_at": datetime.utcnow()}}
    )
    if accept:
        database.project_memberships.update_one(
            {"project_id": row["project_id"], "user_id": row["user_id"]},
            {"$set": {"status": "accepted", "joined_at": datetime.utcnow()},
             "$setOnInsert": {"created_at": datetime.utcnow()}}, upsert=True
        )
    create_notification(
        row["user_id"], "join_accepted" if accept else "join_rejected",
        "Заявка принята" if accept else "Заявка отклонена",
        (f"Ваша заявка в проект «{project.get('name', '')}» принята. Теперь вы участник проекта."
         if accept else f"Владелец проекта «{project.get('name', '')}» отклонил вашу заявку."),
        row["project_id"]
    )
    return {"status": status}, None


def list_project_members(project_id):
    project_oid = _parse_id(project_id)
    if project_oid is None:
        return []
    project = get_db().projects.find_one({"_id": project_oid})
    if not project:
        return []
    user_ids = [row["user_id"] for row in get_db().project_memberships.find(
        {"project_id": project_oid, "status": "accepted"}, {"user_id": 1}
    )]
    if project.get("owner_id"):
        user_ids.append(project["owner_id"])
    result = []
    for user in get_db().users.find({"_id": {"$in": list(set(user_ids))}}):
        result.append({
            "_id": str(user["_id"]),
            "username": user.get("username", ""),
            "full_name": user.get("full_name") or "",
            "email": user.get("email", ""),
            "role": "owner" if user["_id"] == project.get("owner_id") else "member",
        })
    return result


def add_project_invitation(project_id, inviter_id, invitee_id):
    p_oid, from_oid, to_oid = map(_parse_id, (project_id, inviter_id, invitee_id))
    if not all((p_oid, from_oid, to_oid)) or from_oid == to_oid:
        return None, "Некорректные данные приглашения"
    database = get_db()
    if database.projects.find_one({"_id": p_oid}) is None:
        return None, "Проект не найден"
    if database.users.find_one({"_id": to_oid}) is None:
        return None, "Пользователь не найден"
    if is_project_member(project_id, invitee_id):
        return None, "Пользователь уже состоит в проекте"
    existing = database.project_invitations.find_one({
        "project_id": p_oid, "invitee_id": to_oid, "status": "pending"
    })
    if existing:
        return None, "Приглашение этому пользователю уже отправлено"
    doc = {
        "project_id": p_oid, "inviter_id": from_oid, "invitee_id": to_oid,
        "status": "pending", "created_at": datetime.utcnow()
    }
    result = database.project_invitations.insert_one(doc)
    doc["_id"] = result.inserted_id
    project = database.projects.find_one({"_id": p_oid})
    create_notification(
        to_oid, "project_invitation", "Новое приглашение в проект",
        f"Вас пригласили в проект «{(project or {}).get('name', '')}». Проверьте входящие приглашения.",
        project_id
    )
    return _invitation_to_dict(doc), None


def _invitation_to_dict(doc):
    if not doc:
        return None
    for key in ("_id", "project_id", "inviter_id", "invitee_id"):
        if doc.get(key) is not None:
            doc[key] = str(doc[key])
    return doc


def list_invitations_for_user(user_id, status="pending"):
    user_oid = _parse_id(user_id)
    if user_oid is None:
        return []
    rows = get_db().project_invitations.find({"invitee_id": user_oid, "status": status}).sort("created_at", -1)
    result = []
    for row in rows:
        item = _invitation_to_dict(row)
        project = get_project_by_id(item["project_id"])
        inviter = get_user_by_id(item["inviter_id"])
        item["project_name"] = project.get("name") if project else "Проект удалён"
        item["inviter_username"] = inviter.get("username") if inviter else "Удалённый пользователь"
        result.append(item)
    return result


def respond_project_invitation(invitation_id, user_id, accept):
    inv_oid, user_oid = _parse_id(invitation_id), _parse_id(user_id)
    if inv_oid is None or user_oid is None:
        return None, "Приглашение не найдено"
    database = get_db()
    invitation = database.project_invitations.find_one({
        "_id": inv_oid, "invitee_id": user_oid, "status": "pending"
    })
    if not invitation:
        return None, "Приглашение не найдено или уже обработано"
    new_status = "accepted" if accept else "rejected"
    database.project_invitations.update_one(
        {"_id": inv_oid, "status": "pending"},
        {"$set": {"status": new_status, "responded_at": datetime.utcnow()}}
    )
    if accept:
        database.project_memberships.update_one(
            {"project_id": invitation["project_id"], "user_id": user_oid},
            {"$set": {"status": "accepted", "joined_at": datetime.utcnow()},
             "$setOnInsert": {"created_at": datetime.utcnow()}},
            upsert=True
        )
    project = database.projects.find_one({"_id": invitation["project_id"]})
    user = get_user_by_id(user_id)
    if project:
        create_notification(
            project.get("owner_id"),
            "invitation_accepted" if accept else "invitation_rejected",
            "Приглашение принято" if accept else "Приглашение отклонено",
            f"Пользователь @{(user or {}).get('username', 'участник')} {'принял' if accept else 'отклонил'} приглашение в проект «{project.get('name', '')}».",
            invitation["project_id"]
        )
    return _invitation_to_dict(database.project_invitations.find_one({"_id": inv_oid})), None


def remove_project_member(project_id, user_id):
    p_oid, u_oid = _parse_id(project_id), _parse_id(user_id)
    if p_oid is None or u_oid is None:
        return False
    project = get_db().projects.find_one({"_id": p_oid})
    result = get_db().project_memberships.delete_one({"project_id": p_oid, "user_id": u_oid})
    if result.deleted_count and project:
        create_notification(
            u_oid, "removed_from_project", "Доступ к проекту закрыт",
            f"Вас исключили из проекта «{project.get('name', '')}».",
            project_id
        )
    get_db().project_invitations.update_many(
        {"project_id": p_oid, "invitee_id": u_oid, "status": "pending"},
        {"$set": {"status": "cancelled", "responded_at": datetime.utcnow()}}
    )
    if result.deleted_count:
        get_db().tasks.update_many(
            {"project_id": p_oid, "assignee_id": u_oid},
            {"$set": {"assignee_id": None, "assignee_unassigned": True}}
        )
    return result.deleted_count > 0


def list_project_invitations(project_id, status="pending"):
    project_oid = _parse_id(project_id)
    if project_oid is None:
        return []
    rows = get_db().project_invitations.find({"project_id": project_oid, "status": status}).sort("created_at", -1)
    result = []
    for row in rows:
        item = _invitation_to_dict(row)
        user = get_user_by_id(item["invitee_id"])
        item["invitee_username"] = user.get("username") if user else "Удалённый пользователь"
        result.append(item)
    return result


def cancel_project_invitation(project_id, invitation_id):
    project_oid, invitation_oid = _parse_id(project_id), _parse_id(invitation_id)
    if project_oid is None or invitation_oid is None:
        return False
    result = get_db().project_invitations.update_one(
        {"_id": invitation_oid, "project_id": project_oid, "status": "pending"},
        {"$set": {"status": "cancelled", "responded_at": datetime.utcnow()}}
    )
    return result.modified_count == 1


def list_project_invite_candidates(project_id):
    project_oid = _parse_id(project_id)
    if project_oid is None:
        return []
    project = get_db().projects.find_one({"_id": project_oid})
    if not project:
        return []
    existing = {row["user_id"] for row in get_db().project_memberships.find(
        {"project_id": project_oid}, {"user_id": 1}
    )}
    existing.add(project["owner_id"])
    pending = {row["invitee_id"] for row in get_db().project_invitations.find(
        {"project_id": project_oid, "status": "pending"}, {"invitee_id": 1}
    )}
    excluded = list(existing | pending)
    users = get_db().users.find({"_id": {"$nin": excluded}})
    return [{"_id": str(u["_id"]), "username": u.get("username", ""),
             "full_name": u.get("full_name") or ""} for u in users]


# ============================================================
# TASKS
# ============================================================

def create_task(project_id, title, description=None, assignee_id=None, status="TODO", created_by_id=None):
    project_oid = _parse_id(project_id)
    if project_oid is None:
        return None
    assignee_oid = _parse_id(assignee_id) if assignee_id else None

    db = get_db()
    last = db.tasks.find_one(
        {"project_id": project_oid, "status": status},
        sort=[("position", -1)]
    )
    position = (last["position"] + 1) if last else 0

    doc = {
        "project_id": project_oid,
        "assignee_id": assignee_oid,
        "created_by_id": _parse_id(created_by_id) if created_by_id else None,
        "title": title,
        "description": description,
        "status": status,
        "position": position,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = db.tasks.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _task_to_dict(doc)


def get_task_by_id(task_id):
    oid = _parse_id(task_id)
    if oid is None:
        return None
    return _task_to_dict(get_db().tasks.find_one({"_id": oid}))


def list_tasks(project_id=None, assignee_id=None, status=None):
    query = {}
    if project_id:
        oid = _parse_id(project_id)
        if oid is None:
            return []
        query["project_id"] = oid
    if assignee_id:
        oid = _parse_id(assignee_id)
        if oid is None:
            return []
        query["assignee_id"] = oid
    if status:
        query["status"] = status

    docs = get_db().tasks.find(query).sort([("status", 1), ("position", 1)])
    return [_task_to_dict(d) for d in docs]


def list_tasks_by_project(project_id):
    """Удобная обёртка: все задачи проекта."""
    return list_tasks(project_id=project_id)


def list_tasks_by_assignee(assignee_id):
    """Удобная обёртка: все задачи исполнителя (для страницы 'Мои задачи')."""
    return list_tasks(assignee_id=assignee_id)


def update_task(task_id, **fields):
    oid = _parse_id(task_id)
    if oid is None:
        return None

    allowed = {"title", "description", "status", "position", "assignee_id"}
    update = {}
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key == "assignee_id":
            update[key] = _parse_id(value) if value else None
        else:
            update[key] = value
    if not update:
        return get_task_by_id(task_id)

    update["updated_at"] = datetime.utcnow()
    get_db().tasks.update_one({"_id": oid}, {"$set": update})
    return get_task_by_id(task_id)


def assign_task(task_id, assignee_id):
    return update_task(task_id, assignee_id=assignee_id)


def move_task(task_id, new_status, new_position=None):
    """
    Перемещает задачу в другую колонку (статус) и/или позицию.
    Если new_position не указан — ставит в конец колонки.
    """
    oid = _parse_id(task_id)
    if oid is None:
        return None

    db = get_db()
    task = db.tasks.find_one({"_id": oid})
    if not task:
        return None

    if new_position is None:
        last = db.tasks.find_one(
            {"project_id": task["project_id"], "status": new_status},
            sort=[("position", -1)]
        )
        new_position = (last["position"] + 1) if last else 0

    update = {
        "status": new_status,
        "position": new_position,
        "updated_at": datetime.utcnow(),
    }
    db.tasks.update_one({"_id": oid}, {"$set": update})
    return get_task_by_id(task_id)


def delete_task(task_id):
    oid = _parse_id(task_id)
    if oid is None:
        return False
    result = get_db().tasks.delete_one({"_id": oid})
    return result.deleted_count == 1


def delete_tasks_by_project(project_id):
    """Удаляет все задачи проекта (используется при delete_project)."""
    oid = _parse_id(project_id)
    if oid is None:
        return 0
    result = get_db().tasks.delete_many({"project_id": oid})
    return result.deleted_count