import os

from flask import Flask, jsonify, render_template, redirect, session, request, url_for

from db import init_db
from routes.users import users_bp
from routes.projects import projects_bp
from routes.tasks import tasks_bp


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv(
        "SECRET_KEY",
        "dev-only-change-this-secret-key"
    )

    init_db(app)

    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)

    @app.before_request
    def require_login():
        public_endpoints = {
            "auth_page",
            "users.register",
            "users.login",
            "health",
            "static",
        }

        if request.endpoint in public_endpoints:
            return None

        if not session.get("user_id"):
            if request.path.startswith(("/users/", "/projects/", "/tasks/")):
                return jsonify({"error": "Требуется авторизация"}), 401
            return redirect(url_for("auth_page"))

        return None

    @app.route("/")
    def auth_page():
        if session.get("user_id"):
            return redirect(url_for("index"))
        return render_template("auth.html")

    @app.route("/dashboard")
    def index():
        return render_template("index.html")

    @app.route("/projects-page")
    def projects_page():
        return render_template("projects.html")

    @app.route("/tasks-page")
    def tasks_page():
        return render_template("tasks.html")

    @app.route("/users-page")
    def users_page():
        return render_template("users.html")

    @app.route("/task-form")
    def task_form_page():
        return render_template("task_form.html")

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "message": "Flask API is running"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
