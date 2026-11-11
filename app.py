from flask import Flask, jsonify, render_template
from db import init_db
from routes.users import users_bp
from routes.projects import projects_bp
from routes.tasks import tasks_bp


def create_app():
    app = Flask(__name__)

    init_db(app)

    app.register_blueprint(users_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)

    @app.route("/")
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
