from flask import Flask
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
        return {"message": "Kanban API on Flask is running"}

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)