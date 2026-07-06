from flask import Blueprint, jsonify, request
from app.db.database import db
from app.db.models import Dashboard, Datasource, DashboardHistory
from app.services.data_bridge import fetch_component_data, _execute_mysql, _execute_sqlite, _execute_http
from app.services.auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)

# ── Dashboard CRUD ─────────────────────────────────────────

@dashboard_bp.route("/api/dashboard/list")
@login_required
def list_dashboards():
    return jsonify([r.to_dict() for r in Dashboard.query.order_by(Dashboard.updated_at.desc()).all()])

@dashboard_bp.route("/api/dashboard/<int:board_id>", methods=["DELETE"])
@login_required
def delete_dashboard(board_id):
    board = Dashboard.query.get_or_404(board_id)
    DashboardHistory.query.filter_by(dashboard_id=board_id).delete()
    db.session.delete(board)
    db.session.commit()
    return jsonify({"ok": True})

@dashboard_bp.route("/api/dashboard/<int:board_id>")
@login_required
def get_dashboard(board_id):
    return jsonify(Dashboard.query.get_or_404(board_id).to_dict())

@dashboard_bp.route("/api/dashboard", methods=["POST"])
@login_required
def create_dashboard():
    data = request.get_json()
    board = Dashboard(name=data["name"], canvas_json=data.get("canvas_json", {}))
    db.session.add(board)
    db.session.commit()
    return jsonify(board.to_dict()), 201

@dashboard_bp.route("/api/dashboard/<int:board_id>", methods=["PUT"])
@login_required
def update_dashboard(board_id):
    board = Dashboard.query.get_or_404(board_id)
    data = request.get_json()
    latest = DashboardHistory.query.filter_by(dashboard_id=board_id).order_by(
        DashboardHistory.version.desc()).first()
    new_version = (latest.version + 1) if latest else 1
    db.session.add(DashboardHistory(
        dashboard_id=board_id, version=new_version,
        canvas_json=board.canvas_json, change_note=data.get("change_note", "")))
    board.canvas_json = data["canvas_json"]
    board.name = data.get("name", board.name)
    db.session.commit()
    return jsonify(board.to_dict())

# ── Version history ────────────────────────────────────────

@dashboard_bp.route("/api/dashboard/<int:board_id>/history")
@login_required
def get_history(board_id):
    return jsonify([r.to_dict() for r in DashboardHistory.query.filter_by(
        dashboard_id=board_id).order_by(DashboardHistory.version.desc()).all()])

@dashboard_bp.route("/api/dashboard/<int:board_id>/rollback/<int:version>", methods=["POST"])
@login_required
def rollback(board_id, version):
    board = Dashboard.query.get_or_404(board_id)
    hist = DashboardHistory.query.filter_by(dashboard_id=board_id, version=version).first_or_404()
    latest = DashboardHistory.query.filter_by(dashboard_id=board_id).order_by(
        DashboardHistory.version.desc()).first()
    new_version = (latest.version + 1) if latest else 1
    db.session.add(DashboardHistory(
        dashboard_id=board_id, version=new_version,
        canvas_json=board.canvas_json,
        change_note=f"Rollback to v{version} auto-snapshot"))
    board.canvas_json = hist.canvas_json
    db.session.commit()
    return jsonify({"ok": True, "rolled_back_to": version, "snapshot_version": new_version})

# ── Data bridge API ────────────────────────────────────────

@dashboard_bp.route("/api/component/data/<int:board_id>/<component_id>")
@login_required
def component_data(board_id, component_id):
    try:
        return jsonify(fetch_component_data(board_id, component_id))
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Datasource management ──────────────────────────────────

@dashboard_bp.route("/api/datasources")
@login_required
def list_datasources():
    return jsonify([r.to_dict() for r in Datasource.query.all()])

@dashboard_bp.route("/api/datasource", methods=["POST"])
@login_required
def create_datasource():
    data = request.get_json()
    ds = Datasource(name=data["name"], type=data["type"], config=data["config"])
    db.session.add(ds)
    db.session.commit()
    return jsonify(ds.to_dict()), 201

@dashboard_bp.route("/api/datasource/<int:ds_id>", methods=["DELETE"])
@login_required
def delete_datasource(ds_id):
    ds = Datasource.query.get_or_404(ds_id)
    db.session.delete(ds)
    db.session.commit()
    return jsonify({"ok": True})

@dashboard_bp.route("/api/datasource/<int:ds_id>/test", methods=["POST"])
@login_required
def test_datasource(ds_id):
    ds = Datasource.query.get_or_404(ds_id)
    try:
        if ds.type in ("mysql", "postgresql"):
            _execute_mysql(ds, "SELECT 1")
        elif ds.type == "sqlite":
            _execute_sqlite(ds, "SELECT 1")
        elif ds.type == "http_api":
            _execute_http(ds, {})
        return jsonify({"ok": True, "message": "连接成功"})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 400
