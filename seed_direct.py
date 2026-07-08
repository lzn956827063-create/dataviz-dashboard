"""Seed demo dashboards directly into the database (no API required)."""
import json
import os
import sqlite3
import sys

SELF_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SELF_DIR, "app", "data")
DB_PATH = os.path.join(DATA_DIR, "dataviz.db")

os.makedirs(DATA_DIR, exist_ok=True)

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

def exec_sql(sql, params=()):
    conn.execute(sql, params)

def insert(table, **kwargs):
    cols = ", ".join(kwargs.keys())
    placeholders = ", ".join("?" for _ in kwargs)
    conn.execute(f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders})", tuple(kwargs.values()))

# Ensure tables exist — create app context to let SQLAlchemy do it
from app import create_app
app = create_app()
ctx = app.app_context()
ctx.push()

# Clean existing demo dashboards
conn.execute("DELETE FROM t_dashboard_history")
conn.execute("DELETE FROM t_dashboard WHERE is_demo = 1")
conn.execute("DELETE FROM t_datasource")

# Admin password reset to admin123
conn.execute("UPDATE t_user SET password_hash = ? WHERE username = ?",
             ("scrypt:32768:8:1$D3uRF6BVy5qZcuDH$1d2f2a9d1a92de8fca9a3f20a0f4f3b29e02a1a7c3b6c0e9f4a613260c3ebd2bd6c9e5a2b7e62cf8d3f7a99b4c2d5e6f2e1a0b3c7d8e5f9a6b3c1d4e7", "admin"))

# ── 0. Seed sample data tables into SQLite ──────────────
conn.executescript("""
DROP TABLE IF EXISTS demo_sales;
CREATE TABLE demo_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    month TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL
);
INSERT INTO demo_sales VALUES
    (1,'2026-01','电子产品',125000),(2,'2026-02','电子产品',138000),(3,'2026-03','电子产品',152000),
    (4,'2026-04','电子产品',147000),(5,'2026-05','电子产品',169000),(6,'2026-06','电子产品',183000),
    (7,'2026-01','服装鞋帽',82000),(8,'2026-02','服装鞋帽',79000),(9,'2026-03','服装鞋帽',91000),
    (10,'2026-04','服装鞋帽',88000),(11,'2026-05','服装鞋帽',96000),(12,'2026-06','服装鞋帽',102000),
    (13,'2026-01','食品饮料',65000),(14,'2026-02','食品饮料',68000),(15,'2026-03','食品饮料',72000),
    (16,'2026-04','食品饮料',71000),(17,'2026-05','食品饮料',75000),(18,'2026-06','食品饮料',80000),
    (19,'2026-01','家居用品',45000),(20,'2026-02','家居用品',48000),(21,'2026-03','家居用品',52000),
    (22,'2026-04','家居用品',50000),(23,'2026-05','家居用品',55000),(24,'2026-06','家居用品',60000);

DROP TABLE IF EXISTS demo_users;
CREATE TABLE demo_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel TEXT NOT NULL,
    user_type TEXT NOT NULL,
    count INTEGER NOT NULL
);
INSERT INTO demo_users VALUES
    (1,'搜索引擎','新用户',3200),(2,'社交媒体','新用户',2800),(3,'直接访问','新用户',1500),
    (4,'邮件营销','新用户',900),(5,'其他渠道','新用户',600),
    (6,'搜索引擎','老用户',4500),(7,'社交媒体','老用户',3200),(8,'直接访问','老用户',2800),
    (9,'邮件营销','老用户',1800),(10,'其他渠道','老用户',700);

DROP TABLE IF EXISTS demo_servers;
CREATE TABLE demo_servers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cpu_pct REAL NOT NULL,
    mem_pct REAL NOT NULL,
    disk_pct REAL NOT NULL,
    status TEXT NOT NULL
);
INSERT INTO demo_servers VALUES
    (1,'Web-01',32.5,58.2,45.0,'正常'),(2,'Web-02',28.1,52.8,40.3,'正常'),
    (3,'Web-03',35.7,61.4,47.2,'正常'),(4,'DB-Master',45.2,78.9,62.5,'警告'),
    (5,'DB-Slave',22.3,55.1,38.7,'正常'),(6,'Cache-01',15.8,42.3,25.1,'正常'),
    (7,'MQ-01',18.9,35.6,30.2,'正常'),(8,'Log-01',12.3,28.7,55.8,'正常');
""")
conn.commit()
print("Sample data tables created (demo_sales, demo_users, demo_servers)")

# ── 0. Create datasources ────────────────────────────────
conn.execute("INSERT INTO t_datasource (name, type, config) VALUES (?, ?, ?)",
             ("演示数据库 (SQLite)", "sqlite", json.dumps({"database": DB_PATH})))
ds_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
conn.execute("INSERT INTO t_datasource (name, type, config) VALUES (?, ?, ?)",
             ("GitHub API", "http_api", json.dumps({"url": "https://api.github.com", "method": "GET"})))
ds_http = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
conn.execute("INSERT INTO t_datasource (name, type, config) VALUES (?, ?, ?)",
             ("JSONPlaceholder API", "http_api", json.dumps({"url": "https://jsonplaceholder.typicode.com", "method": "GET"})))
ds_json = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
conn.commit()
print(f"Datasources: {ds_id}=SQLite, {ds_http}=GitHub, {ds_json}=JSONPlaceholder")

# ── 1. 电商销售数据大盘 ───────────────────────────────────
board1 = json.dumps({
    "version": 1, "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
    "components": [
        {"id": "s_001", "type": "stat_card", "title": "上半年总销售额",
         "layout": {"x": 0, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT printf('%.1f', SUM(amount)/10000) AS val FROM demo_sales"},
         "display_config": {"prefix": "", "format": "number", "field": "val"}},
        {"id": "s_002", "type": "stat_card", "title": "月均销售额",
         "layout": {"x": 3, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT printf('%.1f', AVG(m.amt)/10000) AS val FROM (SELECT SUM(amount) AS amt FROM demo_sales GROUP BY month) m"},
         "display_config": {"prefix": "", "format": "number", "field": "val"}},
        {"id": "s_003", "type": "stat_card", "title": "最高单月",
         "layout": {"x": 6, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT printf('%.1f', MAX(m.amt)/10000) AS val FROM (SELECT SUM(amount) AS amt FROM demo_sales GROUP BY month) m"},
         "display_config": {"prefix": "", "format": "number", "field": "val"}},
        {"id": "s_004", "type": "stat_card", "title": "品类数量",
         "layout": {"x": 9, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT COUNT(DISTINCT category) AS val FROM demo_sales"},
         "display_config": {"field": "val"}},
        {"id": "s_005", "type": "echarts_line", "title": "各品类月度销售趋势",
         "layout": {"x": 0, "y": 2, "w": 8, "h": 5}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT month, category, SUM(amount) AS total FROM demo_sales GROUP BY month, category ORDER BY month"},
         "chart_config": {"xAxis": "month", "series": [
             {"field": "total", "name": "电子产品", "type": "line", "color": "#4361ee"},
         ]}},
        {"id": "s_006", "type": "echarts_pie", "title": "品类销售额占比",
         "layout": {"x": 8, "y": 2, "w": 4, "h": 5}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT category AS name, SUM(amount) AS value FROM demo_sales GROUP BY category"},
         "chart_config": {"nameField": "name", "valueField": "value"}},
    ],
})
conn.execute("INSERT INTO t_dashboard (name, canvas_json, is_published, is_demo) VALUES (?, ?, 1, 1)",
             ("电商销售数据大盘", board1))

# ── 2. 服务器集群监控 ──────────────────────────────────────
board2 = json.dumps({
    "version": 1, "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
    "components": [
        {"id": "m_001", "type": "stat_card", "title": "服务器总数",
         "layout": {"x": 0, "y": 0, "w": 2, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT COUNT(*) AS val FROM demo_servers"},
         "display_config": {"field": "val"}},
        {"id": "m_002", "type": "stat_card", "title": "正常运行",
         "layout": {"x": 2, "y": 0, "w": 2, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT COUNT(*) AS val FROM demo_servers WHERE status='正常'"},
         "display_config": {"field": "val"}},
        {"id": "m_003", "type": "stat_card", "title": "告警",
         "layout": {"x": 4, "y": 0, "w": 2, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT COUNT(*) AS val FROM demo_servers WHERE status='警告'"},
         "display_config": {"field": "val"}},
        {"id": "m_004", "type": "stat_card", "title": "平均 CPU",
         "layout": {"x": 6, "y": 0, "w": 2, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT printf('%.1f', AVG(cpu_pct)) AS val FROM demo_servers"},
         "display_config": {"prefix": "", "format": "number", "field": "val"}},
        {"id": "m_005", "type": "stat_card", "title": "平均内存",
         "layout": {"x": 8, "y": 0, "w": 2, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT printf('%.1f', AVG(mem_pct)) AS val FROM demo_servers"},
         "display_config": {"prefix": "", "format": "number", "field": "val"}},
        {"id": "m_006", "type": "stat_card", "title": "平均磁盘",
         "layout": {"x": 10, "y": 0, "w": 2, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT printf('%.1f', AVG(disk_pct)) AS val FROM demo_servers"},
         "display_config": {"prefix": "", "format": "number", "field": "val"}},
        {"id": "m_007", "type": "echarts_bar", "title": "服务器资源使用率",
         "layout": {"x": 0, "y": 2, "w": 12, "h": 5}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT name, cpu_pct, mem_pct, disk_pct FROM demo_servers ORDER BY cpu_pct DESC"},
         "chart_config": {"xAxis": "name", "series": [
             {"field": "cpu_pct", "name": "CPU %", "type": "bar", "color": "#e74c3c"},
             {"field": "mem_pct", "name": "内存 %", "type": "bar", "color": "#f39c12"},
             {"field": "disk_pct", "name": "磁盘 %", "type": "bar", "color": "#3498db"},
         ]}},
    ],
})
conn.execute("INSERT INTO t_dashboard (name, canvas_json, is_published, is_demo) VALUES (?, ?, 1, 1)",
             ("服务器集群监控", board2))

# ── 3. 用户增长分析 ───────────────────────────────────────
board3 = json.dumps({
    "version": 1, "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
    "components": [
        {"id": "u_001", "type": "stat_card", "title": "总用户数",
         "layout": {"x": 0, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT SUM(count) AS val FROM demo_users"},
         "display_config": {"field": "val"}},
        {"id": "u_002", "type": "stat_card", "title": "新用户",
         "layout": {"x": 3, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT SUM(count) AS val FROM demo_users WHERE user_type='新用户'"},
         "display_config": {"field": "val"}},
        {"id": "u_003", "type": "stat_card", "title": "老用户",
         "layout": {"x": 6, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT SUM(count) AS val FROM demo_users WHERE user_type='老用户'"},
         "display_config": {"field": "val"}},
        {"id": "u_004", "type": "stat_card", "title": "渠道数",
         "layout": {"x": 9, "y": 0, "w": 3, "h": 2}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT COUNT(DISTINCT channel) AS val FROM demo_users"},
         "display_config": {"field": "val"}},
        {"id": "u_005", "type": "echarts_bar", "title": "各渠道用户分布",
         "layout": {"x": 0, "y": 2, "w": 7, "h": 5}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT channel, user_type, SUM(count) AS total FROM demo_users GROUP BY channel, user_type ORDER BY channel"},
         "chart_config": {"xAxis": "channel", "series": [
             {"field": "total", "name": "新用户", "type": "bar", "color": "#6c83f7"},
             {"field": "total", "name": "老用户", "type": "bar", "color": "#20bf6b"},
         ]}},
        {"id": "u_006", "type": "echarts_pie", "title": "渠道占比",
         "layout": {"x": 7, "y": 2, "w": 5, "h": 5}, "datasource_id": ds_id,
         "query_config": {"sql": "SELECT channel AS name, SUM(count) AS value FROM demo_users GROUP BY channel"},
         "chart_config": {"nameField": "name", "valueField": "value"}},
    ],
})
conn.execute("INSERT INTO t_dashboard (name, canvas_json, is_published, is_demo) VALUES (?, ?, 1, 1)",
             ("用户增长分析", board3))

# ── 4. GitHub 项目数据 ────────────────────────────────────
board4 = json.dumps({
    "version": 1, "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
    "components": [
        {"id": "g_001", "type": "stat_card", "title": "GitHub API Status",
         "layout": {"x": 2, "y": 0, "w": 4, "h": 2}, "datasource_id": ds_http,
         "query_config": {"url": "https://api.github.com", "method": "GET"},
         "display_config": {"field": "current_user_url"}},
        {"id": "g_002", "type": "stat_card", "title": "JSONPlaceholder Posts",
         "layout": {"x": 6, "y": 0, "w": 4, "h": 2}, "datasource_id": ds_json,
         "query_config": {"url": "https://jsonplaceholder.typicode.com/posts", "method": "GET"},
         "display_config": {"field": "length"}},
    ],
})
conn.execute("INSERT INTO t_dashboard (name, canvas_json, is_published, is_demo) VALUES (?, ?, 1, 1)",
             ("GitHub 项目数据", board4))

conn.commit()
conn.close()

print("\n=== ALL DONE ===")
print("4 demo dashboards seeded directly to database.")
print("Open https://lzn.pythonanywhere.com to see them on the homepage.")
print("admin password set to: admin123")

ctx.pop()
