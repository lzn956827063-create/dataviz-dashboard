"""Seed demo dashboards with meaningful sample data."""
import json
import sqlite3
import urllib.request
import os
import urllib.error

DB_PATH = r"D:\Claude\dataviz-dashboard\app\data\dataviz.db"
BASE = "http://127.0.0.1:5001"

TOKEN = None

def api(method, path, data=None):
    url = BASE + path
    body = json.dumps(data).encode("utf-8") if data else None
    headers = {"Content-Type": "application/json"} if body else {}
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()}")
        raise

# Login as admin
print("Logging in as admin...")
try:
    r = api("POST", "/api/auth/login", {"username": "admin", "password": "admin123"})
    TOKEN = r["token"]
    print(f"  Logged in as {r['user']['username']}")
except Exception as e:
    print(f"  Login failed, trying register: {e}")
    r = api("POST", "/api/auth/register", {"username": "admin", "password": "admin123"})
    TOKEN = r["token"]
    print(f"  Registered and logged in")

# Clean slate — delete all existing dashboards
existing = api("GET", "/api/dashboard/list")
for b in existing:
    api("DELETE", f"/api/dashboard/{b['id']}")
    print(f"Deleted board #{b['id']}")

# Clean datasources too
ds_list = api("GET", "/api/datasources")
for d in ds_list:
    try:
        api("DELETE", f"/api/datasource/{d['id']}")
        print(f"Deleted datasource #{d['id']}")
    except:
        pass

# ── 1. Seed sample data tables into SQLite ──────────────────
conn = sqlite3.connect(DB_PATH)
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
conn.close()
print("Sample data tables created (demo_sales, demo_users, demo_servers)")

# ── 2. Create datasources ──────────────────────────────────
ds_sqlite = api("POST", "/api/datasource", {
    "name": "演示数据库 (SQLite)",
    "type": "sqlite",
    "config": {"database": DB_PATH},
})
ds_http = api("POST", "/api/datasource", {
    "name": "GitHub API",
    "type": "http_api",
    "config": {"url": "https://api.github.com", "method": "GET"},
})
ds_jsonplaceholder = api("POST", "/api/datasource", {
    "name": "JSONPlaceholder API",
    "type": "http_api",
    "config": {"url": "https://jsonplaceholder.typicode.com", "method": "GET"},
})
print(f"Datasources: {ds_sqlite['id']}=SQLite, {ds_http['id']}=GitHub, {ds_jsonplaceholder['id']}=JSONPlaceholder")

ds = ds_sqlite["id"]

# ── 3. Dashboard 1: 电商销售数据大盘 ───────────────────────
board1 = api("POST", "/api/dashboard", {
    "name": "电商销售数据大盘",
    "canvas_json": {
        "version": 1,
        "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
        "components": [
            {"id": "s_001", "type": "stat_card", "title": "上半年总销售额",
             "layout": {"x": 0, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT printf('%.1f', SUM(amount)/10000) AS val FROM demo_sales"},
             "display_config": {"prefix": "", "format": "number", "field": "val"}},
            {"id": "s_002", "type": "stat_card", "title": "月均销售额",
             "layout": {"x": 3, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT printf('%.1f', AVG(m.amt)/10000) AS val FROM (SELECT SUM(amount) AS amt FROM demo_sales GROUP BY month) m"},
             "display_config": {"prefix": "", "format": "number", "field": "val"}},
            {"id": "s_003", "type": "stat_card", "title": "最高单月",
             "layout": {"x": 6, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT printf('%.1f', MAX(m.amt)/10000) AS val FROM (SELECT SUM(amount) AS amt FROM demo_sales GROUP BY month) m"},
             "display_config": {"prefix": "", "format": "number", "field": "val"}},
            {"id": "s_004", "type": "stat_card", "title": "品类数量",
             "layout": {"x": 9, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT COUNT(DISTINCT category) AS val FROM demo_sales"},
             "display_config": {"field": "val"}},
            {"id": "s_005", "type": "echarts_line", "title": "各品类月度销售趋势",
             "layout": {"x": 0, "y": 2, "w": 8, "h": 5}, "datasource_id": ds,
             "query_config": {"sql": "SELECT month, category, SUM(amount) AS total FROM demo_sales GROUP BY month, category ORDER BY month"},
             "chart_config": {"xAxis": "month", "series": [
                 {"field": "total", "name": "电子产品", "type": "line", "color": "#4361ee"},
             ]}},
            {"id": "s_006", "type": "echarts_pie", "title": "品类销售额占比",
             "layout": {"x": 8, "y": 2, "w": 4, "h": 5}, "datasource_id": ds,
             "query_config": {"sql": "SELECT category AS name, SUM(amount) AS value FROM demo_sales GROUP BY category"},
             "chart_config": {"nameField": "name", "valueField": "value"}},
        ],
    },
})
print(f"Dashboard '电商销售数据大盘' created: #{board1['id']}")

# ── 4. Dashboard 2: 服务器集群监控 ─────────────────────────
board2 = api("POST", "/api/dashboard", {
    "name": "服务器集群监控",
    "canvas_json": {
        "version": 1,
        "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
        "components": [
            {"id": "m_001", "type": "stat_card", "title": "服务器总数",
             "layout": {"x": 0, "y": 0, "w": 2, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT COUNT(*) AS val FROM demo_servers"},
             "display_config": {"field": "val"}},
            {"id": "m_002", "type": "stat_card", "title": "正常运行",
             "layout": {"x": 2, "y": 0, "w": 2, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT COUNT(*) AS val FROM demo_servers WHERE status='正常'"},
             "display_config": {"field": "val"}},
            {"id": "m_003", "type": "stat_card", "title": "告警",
             "layout": {"x": 4, "y": 0, "w": 2, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT COUNT(*) AS val FROM demo_servers WHERE status='警告'"},
             "display_config": {"field": "val"}},
            {"id": "m_004", "type": "stat_card", "title": "平均 CPU",
             "layout": {"x": 6, "y": 0, "w": 2, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT printf('%.1f', AVG(cpu_pct)) AS val FROM demo_servers"},
             "display_config": {"prefix": "", "format": "number", "field": "val"}},
            {"id": "m_005", "type": "stat_card", "title": "平均内存",
             "layout": {"x": 8, "y": 0, "w": 2, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT printf('%.1f', AVG(mem_pct)) AS val FROM demo_servers"},
             "display_config": {"prefix": "", "format": "number", "field": "val"}},
            {"id": "m_006", "type": "stat_card", "title": "平均磁盘",
             "layout": {"x": 10, "y": 0, "w": 2, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT printf('%.1f', AVG(disk_pct)) AS val FROM demo_servers"},
             "display_config": {"prefix": "", "format": "number", "field": "val"}},
            {"id": "m_007", "type": "echarts_bar", "title": "服务器资源使用率",
             "layout": {"x": 0, "y": 2, "w": 12, "h": 5}, "datasource_id": ds,
             "query_config": {"sql": "SELECT name, cpu_pct, mem_pct, disk_pct FROM demo_servers ORDER BY cpu_pct DESC"},
             "chart_config": {"xAxis": "name", "series": [
                 {"field": "cpu_pct", "name": "CPU %", "type": "bar", "color": "#e74c3c"},
                 {"field": "mem_pct", "name": "内存 %", "type": "bar", "color": "#f39c12"},
                 {"field": "disk_pct", "name": "磁盘 %", "type": "bar", "color": "#3498db"},
             ]}},
        ],
    },
})
print(f"Dashboard '服务器集群监控' created: #{board2['id']}")

# ── 5. Dashboard 3: 用户增长分析 ───────────────────────────
board3 = api("POST", "/api/dashboard", {
    "name": "用户增长分析",
    "canvas_json": {
        "version": 1,
        "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
        "components": [
            {"id": "u_001", "type": "stat_card", "title": "总用户数",
             "layout": {"x": 0, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT SUM(count) AS val FROM demo_users"},
             "display_config": {"field": "val"}},
            {"id": "u_002", "type": "stat_card", "title": "新用户",
             "layout": {"x": 3, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT SUM(count) AS val FROM demo_users WHERE user_type='新用户'"},
             "display_config": {"field": "val"}},
            {"id": "u_003", "type": "stat_card", "title": "老用户",
             "layout": {"x": 6, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT SUM(count) AS val FROM demo_users WHERE user_type='老用户'"},
             "display_config": {"field": "val"}},
            {"id": "u_004", "type": "stat_card", "title": "渠道数",
             "layout": {"x": 9, "y": 0, "w": 3, "h": 2}, "datasource_id": ds,
             "query_config": {"sql": "SELECT COUNT(DISTINCT channel) AS val FROM demo_users"},
             "display_config": {"field": "val"}},
            {"id": "u_005", "type": "echarts_bar", "title": "各渠道用户分布",
             "layout": {"x": 0, "y": 2, "w": 7, "h": 5}, "datasource_id": ds,
             "query_config": {"sql": "SELECT channel, user_type, SUM(count) AS total FROM demo_users GROUP BY channel, user_type ORDER BY channel"},
             "chart_config": {"xAxis": "channel", "series": [
                 {"field": "total", "name": "新用户", "type": "bar", "color": "#6c83f7"},
                 {"field": "total", "name": "老用户", "type": "bar", "color": "#20bf6b"},
             ]}},
            {"id": "u_006", "type": "echarts_pie", "title": "渠道占比",
             "layout": {"x": 7, "y": 2, "w": 5, "h": 5}, "datasource_id": ds,
             "query_config": {"sql": "SELECT channel AS name, SUM(count) AS value FROM demo_users GROUP BY channel"},
             "chart_config": {"nameField": "name", "valueField": "value"}},
        ],
    },
})
print(f"Dashboard '用户增长分析' created: #{board3['id']}")

# ── 6. Dashboard 4: GitHub 项目数据 (HTTP API) ─────────────
board4 = api("POST", "/api/dashboard", {
    "name": "GitHub 项目数据",
    "canvas_json": {
        "version": 1,
        "canvas": {"cols": 12, "rowHeight": 80, "background": "#0a0f1d"},
        "components": [
            {"id": "g_001", "type": "stat_card", "title": "GitHub API Status",
             "layout": {"x": 2, "y": 0, "w": 4, "h": 2}, "datasource_id": ds_http["id"],
             "query_config": {"url": "https://api.github.com", "method": "GET"},
             "display_config": {"field": "current_user_url"}},
            {"id": "g_002", "type": "stat_card", "title": "JSONPlaceholder Posts",
             "layout": {"x": 6, "y": 0, "w": 4, "h": 2}, "datasource_id": ds_jsonplaceholder["id"],
             "query_config": {"url": "https://jsonplaceholder.typicode.com/posts", "method": "GET"},
             "display_config": {"field": "length"}},
        ],
    },
})
print(f"Dashboard 'GitHub 项目数据' created: #{board4['id']}")

# ── 7. Mark the sales & server dashboards as published ─────
for bid in [board1["id"], board2["id"], board3["id"]]:
    board = api("GET", f"/api/dashboard/{bid}")
    board["canvas_json"]["version"] = 1
    api("PUT", f"/api/dashboard/{bid}", {"name": board["name"], "canvas_json": board["canvas_json"], "change_note": "Published"})
    print(f"Published board #{bid}")

print("\n=== ALL DONE ===")
print("Demo dashboards:")
for i, name in enumerate([board1, board2, board3, board4], 1):
    print(f"  {i}. {name['name']} → http://127.0.0.1:5001/view/{name['id']}")
print(f"\nDatasources created: {ds_sqlite['id']}=SQLite, {ds_http['id']}=GitHub, {ds_jsonplaceholder['id']}=JSONPlaceholder")
