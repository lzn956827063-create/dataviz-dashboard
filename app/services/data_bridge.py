"""通用数据桥接层 — 动态连接异构数据源、执行 SQL/HTTP、标准化输出"""
import logging
import sqlite3
import threading

import requests

logger = logging.getLogger(__name__)

try:
    import pymysql
    from dbutils.pooled_db import PooledDB
    _has_mysql = True
except ImportError:
    _has_mysql = False

_pool_cache = {}
_cache_lock = threading.Lock()


def _get_mysql_pool(ds_config: dict):
    key = hash(frozenset((k, str(v)) for k, v in sorted(ds_config.items())))
    with _cache_lock:
        if key not in _pool_cache:
            _pool_cache[key] = PooledDB(
                creator=pymysql, maxconnections=6, mincached=2, blocking=True,
                host=ds_config["host"], port=ds_config.get("port", 3306),
                user=ds_config["user"], password=ds_config["password"],
                database=ds_config["database"], charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
        return _pool_cache[key]


def _execute_mysql(datasource, sql: str) -> list[dict]:
    if not _has_mysql:
        raise RuntimeError("pymysql not installed. Run: pip install pymysql dbutils")
    ds_config = datasource.config if isinstance(datasource.config, dict) else {}
    pool = _get_mysql_pool(ds_config)
    conn = pool.connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()


def _execute_sqlite(datasource, sql: str) -> list[dict]:
    ds_config = datasource.config if isinstance(datasource.config, dict) else {}
    conn = sqlite3.connect(ds_config.get("database", ""))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def _execute_http(datasource, query_config: dict) -> list[dict]:
    ds_config = datasource.config if isinstance(datasource.config, dict) else {}
    url = query_config.get("url", ds_config.get("url", ""))
    method = query_config.get("method", ds_config.get("method", "GET")).upper()
    headers = {}
    if ds_config.get("auth_type") == "bearer" and ds_config.get("token"):
        headers["Authorization"] = f"Bearer {ds_config['token']}"
    resp = requests.request(method, url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        for wrapper in ("data", "result", "results", "records"):
            if wrapper in data and isinstance(data[wrapper], list):
                return data[wrapper]
        if "rows" in data and isinstance(data["rows"], list):
            return data["rows"]
    if isinstance(data, list):
        # Add synthetic fields for stat_card queries on arrays
        for item in data:
            if isinstance(item, dict):
                item["length"] = len(data)
        return data
    return [data] if data else []


def normalize_to_echarts(raw_rows: list[dict], component: dict):
    comp_type = component.get("type", "")

    if comp_type == "stat_card":
        field = component.get("display_config", {}).get("field", "")
        value = raw_rows[0].get(field, 0) if raw_rows else 0
        return {"value": value}

    if comp_type == "echarts_pie":
        cc = component.get("chart_config", {})
        nf, vf = cc.get("nameField", "name"), cc.get("valueField", "value")
        sd = [{"name": str(r.get(nf, "")), "value": float(r.get(vf, 0))} for r in raw_rows]
        return {"categories": [d["name"] for d in sd], "series": [{"name": "数据", "data": sd}]}

    cc = component.get("chart_config", {})
    x_field = cc.get("xAxis", "")
    series_conf = cc.get("series", [])
    categories = [str(r.get(x_field, "")) for r in raw_rows]
    series = []
    for sc in series_conf:
        field = sc.get("field", "")
        s_data = [float(r.get(field, 0)) if r.get(field) is not None else None for r in raw_rows]
        series.append({"name": sc.get("name", field), "type": sc.get("type", "line"),
                       "data": s_data, "color": sc.get("color")})
    return {"categories": categories, "series": series}


def fetch_component_data(dashboard_id: int, component_id: str):
    from app.db.models import Dashboard, Datasource

    dashboard = Dashboard.query.get(dashboard_id)
    if not dashboard:
        raise ValueError(f"Dashboard {dashboard_id} not found")

    canvas = dashboard.canvas_json if isinstance(dashboard.canvas_json, dict) else {}
    comp = next((c for c in canvas.get("components", []) if c["id"] == component_id), None)
    if not comp:
        raise ValueError(f"Component {component_id} not found")

    ds = Datasource.query.get(comp["datasource_id"])
    if not ds:
        raise ValueError(f"Datasource {comp['datasource_id']} not found")

    qc = comp.get("query_config", {})

    if ds.type in ("mysql", "postgresql"):
        raw = _execute_mysql(ds, qc.get("sql", "SELECT 1"))
    elif ds.type == "sqlite":
        raw = _execute_sqlite(ds, qc.get("sql", "SELECT 1"))
    elif ds.type == "http_api":
        raw = _execute_http(ds, qc)
    else:
        raise ValueError(f"Unsupported type: {ds.type}")

    result = normalize_to_echarts(raw, comp)
    result["component_id"] = component_id
    result["title"] = comp.get("title", "")
    result["type"] = comp.get("type", "")
    return result
