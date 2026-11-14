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
    for name in ["users", "projects", "tasks"]:
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
    result = get_db().users.delete_one({"_id": oid})
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
    result = database.projects.update_one(
        {"_id": project_oid},
        {"$set": {"owner_id": owner_oid}}
    )
    return get_project_by_id(project_id) if result.matched_count else None


def delete_project(project_id):
    """Удаляет проект и все его задачи (каскадное удаление)."""
    oid = _parse_id(project_id)
    if oid is None:
        return False

    db = get_db()
    # Сначала удаляем задачи проекта
    db.tasks.delete_many({"project_id": oid})
    # Затем сам проект
    result = db.projects.delete_one({"_id": oid})
    return result.deleted_count == 1


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