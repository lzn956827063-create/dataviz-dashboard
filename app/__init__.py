"""Low-Code DataViz Dashboard — Enterprise Visualization Platform."""
import os
from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dataviz-dev-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'dataviz.db')}"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"), exist_ok=True)

    from app.db.database import init_db
    init_db(app)

    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.main_routes import main_bp
    from app.routes.auth_routes import auth_bp
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)

    return app
