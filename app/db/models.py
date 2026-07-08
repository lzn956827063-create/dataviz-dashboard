from datetime import datetime, timezone
from app.db.database import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = "t_user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {"id": self.id, "username": self.username,
                "created_at": self.created_at.isoformat() if self.created_at else None}


class Datasource(db.Model):
    __tablename__ = "t_datasource"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    config = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "type": self.type,
                "config": self.config, "created_at": self.created_at.isoformat() if self.created_at else None}


class Dashboard(db.Model):
    __tablename__ = "t_dashboard"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    canvas_json = db.Column(db.JSON, nullable=False, default=dict)
    is_published = db.Column(db.Boolean, default=False)
    is_demo = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description,
                "canvas_json": self.canvas_json, "is_published": self.is_published,
                "is_demo": self.is_demo,
                "created_at": self.created_at.isoformat() if self.created_at else None,
                "updated_at": self.updated_at.isoformat() if self.updated_at else None}


class DashboardHistory(db.Model):
    __tablename__ = "t_dashboard_history"

    id = db.Column(db.Integer, primary_key=True)
    dashboard_id = db.Column(db.Integer, db.ForeignKey("t_dashboard.id", ondelete="CASCADE"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    canvas_json = db.Column(db.JSON, nullable=False, default=dict)
    change_note = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    dashboard = db.relationship("Dashboard", backref=db.backref("history", lazy="dynamic", order_by="DashboardHistory.version.desc()"))
    __table_args__ = (db.UniqueConstraint("dashboard_id", "version", name="uk_dashboard_version"),)

    def to_dict(self):
        return {"id": self.id, "dashboard_id": self.dashboard_id, "version": self.version,
                "canvas_json": self.canvas_json, "change_note": self.change_note,
                "created_at": self.created_at.isoformat() if self.created_at else None}
