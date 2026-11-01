from flask_pymongo import PyMongo
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
from config import settings

mongo = PyMongo()


# ============================================================
# Инициализация
# ============================================================

def init_db(app):
    """Привязывает клиент к приложению и создаёт индексы."""
    app.config["MONGO_URI"] = settings.MONGODB_URI
    mongo.init_app(app)

    with app.app_context():
        try:
            mongo.cx.admin.command("ping")
            print("✅ MongoDB Atlas connected")
            print(f"📂 База данных: {settings.DB_NAME}")
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            raise

        _create_indexes()


def _create_indexes():
    db = get_db()
    db.users.create_index("email", unique=True)
    db.users.create_index("username", unique=True)
    db.projects.create_index("owner_id")
    db.tasks.create_index("project_id")
    db.tasks.create_index("assignee_id")
    db.tasks.create_index([("project_id", 1), ("status", 1), ("position", 1)])


def get_db():
    """Возвращает объект базы данных для внутреннего использования в db.py."""
    return mongo.cx[settings.DB_NAME]


def _to_str(doc):
    """Преобразует ObjectId в строку для JSON-ответа."""
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    return doc


def _parse_id(id_str):
    """Безопасно приводит строку к ObjectId. Возвращает None при ошибке."""
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None


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


def list_users():
    return [_to_str(u) for u in get_db().users.find()]


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
    out = _to_str(doc)
    out["owner_id"] = str(doc["owner_id"])
    return out


def get_project_by_id(project_id):
    oid = _parse_id(project_id)
    if oid is None:
        return None
    doc = get_db().projects.find_one({"_id": oid})
    if doc:
        doc["owner_id"] = str(doc["owner_id"])
    return _to_str(doc)


def list_projects(owner_id=None):
    query = {}
    if owner_id:
        oid = _parse_id(owner_id)
        if oid is None:
            return []
        query["owner_id"] = oid
    result = []
    for doc in get_db().projects.find(query):
        doc["owner_id"] = str(doc["owner_id"])
        result.append(_to_str(doc))
    return result


# ============================================================
# TASKS
# ============================================================

def create_task(project_id, title, description=None, assignee_id=None, status="TODO"):
    project_oid = _parse_id(project_id)
    if project_oid is None:
        return None
    assignee_oid = _parse_id(assignee_id) if assignee_id else None

    db = get_db()
    # Позиция — в конец колонки
    last = db.tasks.find_one(
        {"project_id": project_oid, "status": status},
        sort=[("position", -1)]
    )
    position = (last["position"] + 1) if last else 0

    doc = {
        "project_id": project_oid,
        "assignee_id": assignee_oid,
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


def _task_to_dict(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    doc["project_id"] = str(doc["project_id"])
    doc["assignee_id"] = str(doc["assignee_id"]) if doc.get("assignee_id") else None
    return doc


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


def update_task(task_id, **fields):
    """Обновляет разрешённые поля задачи. Возвращает обновлённый документ."""
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
    """Назначить исполнителя. assignee_id=None снимает назначение."""
    return update_task(task_id, assignee_id=assignee_id)


def delete_task(task_id):
    oid = _parse_id(task_id)
    if oid is None:
        return False
    result = get_db().tasks.delete_one({"_id": oid})
    return result.deleted_count == 1