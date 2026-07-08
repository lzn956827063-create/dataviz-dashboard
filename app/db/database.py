from flask_sqlalchemy import SQLAlchemy
from flask import Flask

db = SQLAlchemy()


def init_db(app: Flask):
    db.init_app(app)
    with app.app_context():
        from app.db.models import Datasource, Dashboard, DashboardHistory  # noqa
        db.create_all()
        _seed_demo()


def _seed_demo():
    import os
    from app.db.models import Dashboard, Datasource, User

    if Dashboard.query.first() is not None:
        return

    # Default admin user
    if User.query.first() is None:
        admin = User(username="admin")
        admin.set_password("admin123")
        db.session.add(admin)

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "dataviz.db")

    ds = Datasource(name="Demo SQLite", type="sqlite", config={"database": db_path})
    db.session.add(ds)
    db.session.flush()

    demo = {
        "version": 1,
        "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
        "components": [
            {"id": "comp_001", "type": "stat_card", "title": "看板总数", "layout": {"x": 0, "y": 0, "w": 3, "h": 2},
             "datasource_id": ds.id, "query_config": {"sql": "SELECT COUNT(*) AS val FROM t_dashboard"}, "display_config": {"field": "val"}},
            {"id": "comp_002", "type": "stat_card", "title": "数据源数", "layout": {"x": 3, "y": 0, "w": 3, "h": 2},
             "datasource_id": ds.id, "query_config": {"sql": "SELECT COUNT(*) AS val FROM t_datasource"}, "display_config": {"field": "val"}},
            {"id": "comp_003", "type": "stat_card", "title": "历史版本", "layout": {"x": 6, "y": 0, "w": 3, "h": 2},
             "datasource_id": ds.id, "query_config": {"sql": "SELECT COUNT(*) AS val FROM t_dashboard_history"}, "display_config": {"field": "val"}},
            {"id": "comp_004", "type": "stat_card", "title": "组件总数", "layout": {"x": 9, "y": 0, "w": 3, "h": 2},
             "datasource_id": ds.id, "query_config": {"sql": "SELECT 4 AS val"}, "display_config": {"field": "val"}},
        ],
    }

    db.session.add(Dashboard(name="Demo 运维概览", canvas_json=demo, is_published=True, is_demo=True))
    db.session.commit()
