"""NL-to-Dashboard Agent — DeepSeek-powered tool-use for visual analytics."""
import json
import logging
import os
from typing import Generator

from openai import OpenAI

logger = logging.getLogger(__name__)

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODEL = os.getenv("AGENT_MODEL", "deepseek-chat")


# ── Lightweight data executors (no Flask ORM context needed) ────

def _execute_mysql_from_config(cfg: dict, sql: str) -> list[dict]:
    try:
        import pymysql
    except ImportError:
        raise RuntimeError("pymysql not installed")
    conn = pymysql.connect(
        host=cfg["host"], port=cfg.get("port", 3306),
        user=cfg["user"], password=cfg.get("password", ""),
        database=cfg.get("database", ""), charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()
    finally:
        conn.close()


def _execute_sqlite_from_config(cfg: dict, sql: str) -> list[dict]:
    import sqlite3
    conn = sqlite3.connect(cfg.get("database", ""))
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def _execute_http_from_config(cfg: dict, query_cfg: dict) -> list[dict]:
    import requests
    url = query_cfg.get("url", cfg.get("url", ""))
    method = query_cfg.get("method", cfg.get("method", "GET")).upper()
    headers = {}
    if cfg.get("auth_type") == "bearer" and cfg.get("token"):
        headers["Authorization"] = f"Bearer {cfg['token']}"
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
        return data
    return [data] if data else []

SYSTEM_PROMPT = """你是 DataViz Dashboard 的看板搭建器。用户说自然语言，你通过函数调用直接在画布上操作图表。只动手，不废话。

调用规则：
1. 收到请求直接调用工具，不要分析、不要确认、不要解释
2. 多个组件一次性批量调用 add_component 创建
3. 排版用 layout 参数，stat_card w=3 h=2，图表 w=6 h=3，同一行 x 累加不让 gap

排版算法（12 列网格）：
- 每个组件必须 x+w <= 12
- 同一行组件之间不留空隙，挨着放（上一个 x+w 作为下一个的 x）
- stat_card: w=3 h=2，图表: w=6 h=3
- 示例：两个 stat_card → (0,0,3,2) (3,0,3,2)
- 示例：图表+饼图 → (0,0,6,3) (6,0,6,3)
- 示例：三个 stat_card → (0,0,3,2) (3,0,3,2) (6,0,3,2)
- 放不下（x+w>12）才换行 y+上一行最大h

回复规则：
- 不要长篇大论，不要写"正在思考..."、"让我先..."、"查询成功..."、"已创建..."这些过程
- 不要列清单，不要说"组件详情"
- 只需要操作完成后回复一句话，如"已添加 3 个数值卡和一个折线图"
- 如果只是挪位置，回复"排版已优化"

SQL 规则：
- SQLite 语法，表名不加引号
- 查表结构用：SELECT name FROM sqlite_master WHERE type='table'"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_component",
            "description": "向看板画布添加一个新图表组件。你可以指定 layout (x, y, w, h) 来控制位置和大小。如果不指定 layout，系统会自动计算位置。画布是12列网格。",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["echarts_line", "echarts_bar", "echarts_area", "echarts_pie", "stat_card"],
                        "description": "图表类型"
                    },
                    "title": {"type": "string", "description": "组件标题"},
                    "datasource_id": {"type": "integer", "description": "数据源 ID"},
                    "layout": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer", "description": "水平位置（第几列开始，0-11）"},
                            "y": {"type": "integer", "description": "垂直位置（第几行开始）"},
                            "w": {"type": "integer", "description": "宽度（占几列，建议 stat_card=3，图表=4~6）"},
                            "h": {"type": "integer", "description": "高度（占几行，建议 stat_card=2，图表=3）"}
                        },
                        "description": "布局位置。"
                    },
                    "query_config": {
                        "type": "object",
                        "properties": {
                            "sql": {"type": "string", "description": "SQL 查询语句（MySQL/SQLite 数据源使用）"},
                            "url": {"type": "string", "description": "HTTP API URL（http_api 数据源使用）"}
                        },
                        "description": "数据查询配置"
                    },
                    "chart_config": {
                        "type": "object",
                        "properties": {
                            "xAxis": {"type": "string", "description": "X 轴字段名（折线图/柱状图/面积图必填）"},
                            "series": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {"type": "string", "description": "数据字段名"},
                                        "name": {"type": "string", "description": "系列显示名称"},
                                        "type": {"type": "string", "enum": ["line", "bar"], "description": "系列图表类型"},
                                        "color": {"type": "string", "description": "系列颜色（可选，如 #6c83f7）"}
                                    },
                                    "required": ["field", "name"]
                                },
                                "description": "系列配置数组"
                            },
                            "nameField": {"type": "string", "description": "饼图名称字段"},
                            "valueField": {"type": "string", "description": "饼图值字段"}
                        },
                        "description": "图表配置"
                    },
                    "display_config": {
                        "type": "object",
                        "properties": {
                            "field": {"type": "string", "description": "展示的字段名"},
                            "prefix": {"type": "string", "description": "数值前缀，如 ¥、$ 等"}
                        },
                        "description": "显示配置（数值卡需要 field）"
                    }
                },
                "required": ["type", "title", "datasource_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_component",
            "description": "修改画布上已有组件的配置，包括布局位置。只传需要修改的字段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_id": {"type": "string", "description": "组件 ID，如 comp_001"},
                    "title": {"type": "string", "description": "新的标题"},
                    "type": {
                        "type": "string",
                        "enum": ["echarts_line", "echarts_bar", "echarts_area", "echarts_pie", "stat_card"],
                        "description": "新的图表类型"
                    },
                    "datasource_id": {"type": "integer", "description": "新的数据源 ID"},
                    "query_config": {"type": "object", "description": "新的查询配置"},
                    "chart_config": {"type": "object", "description": "新的图表配置"},
                    "display_config": {"type": "object", "description": "新的显示配置"},
                    "layout": {
                        "type": "object",
                        "properties": {
                            "x": {"type": "integer"},
                            "y": {"type": "integer"},
                            "w": {"type": "integer"},
                            "h": {"type": "integer"}
                        },
                        "description": "组件布局位置。优化排版时传此参数直接挪位置，不用删除重建。"
                    }
                },
                "required": ["component_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remove_component",
            "description": "从画布上删除一个组件。",
            "parameters": {
                "type": "object",
                "properties": {
                    "component_id": {"type": "string", "description": "要删除的组件 ID"}
                },
                "required": ["component_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_components",
            "description": "列出当前画布上所有已有组件。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_datasources",
            "description": "列出所有可用的数据源及其配置信息。",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "preview_query",
            "description": "执行一条 SQL 查询并返回前5行数据。用于在创建组件前验证查询是否正确。",
            "parameters": {
                "type": "object",
                "properties": {
                    "datasource_id": {"type": "integer", "description": "数据源 ID"},
                    "sql": {"type": "string", "description": "要执行的 SQL 查询"}
                },
                "required": ["datasource_id", "sql"]
            }
        }
    },
]


class DashboardAgent:
    """Orchestrates DeepSeek tool-use for the dashboard builder."""

    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("API Key 未配置，请设置 DEEPSEEK_API_KEY 环境变量")
        self.client = OpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL)
        self.model = MODEL

    def _sse_event(self, event: str, data: dict | str) -> str:
        """Format a single SSE event."""
        payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False, default=str)
        return f"event: {event}\ndata: {payload}\n\n"

    def _execute_tool(self, tool_name: str, tool_input: dict, dashboard_state: dict, datasources: list[dict]) -> dict:
        """Execute a single tool call and return the result."""
        components = dashboard_state.get("components", [])

        if tool_name == "list_components":
            summary = []
            for c in components:
                summary.append({
                    "id": c["id"], "type": c.get("type", ""), "title": c.get("title", ""),
                    "datasource_id": c.get("datasource_id"),
                })
            return {"components": summary, "count": len(summary)}

        elif tool_name == "get_datasources":
            return {"datasources": datasources, "count": len(datasources)}

        elif tool_name == "add_component":
            existing_ids = {c["id"] for c in components}
            idx = len(components) + 1
            while f"comp_{idx:03d}" in existing_ids:
                idx += 1
            comp_id = f"comp_{idx:03d}"

            comp_type = tool_input["type"]
            # Use user-specified layout if provided, otherwise auto-calculate tight layout
            if "layout" in tool_input and tool_input["layout"]:
                layout = tool_input["layout"]
            else:
                # Tight layout: no gaps, fill row before wrapping
                w = 3 if comp_type == "stat_card" else 6
                h = 2 if comp_type == "stat_card" else 3
                layout = {"x": 0, "y": 0, "w": w, "h": h}
                rows = {}
                for c in components:
                    cl = c.get("layout", {})
                    cy = cl.get("y", 0)
                    cw = cl.get("w", 6)
                    ch = cl.get("h", 3)
                    if cy not in rows:
                        rows[cy] = {"x_end": 0, "max_h": 0}
                    rows[cy]["x_end"] += cw
                    rows[cy]["max_h"] = max(rows[cy]["max_h"], ch)
                for y in sorted(rows.keys()):
                    info = rows[y]
                    if info["x_end"] + w <= 12:
                        layout = {"x": info["x_end"], "y": y, "w": w, "h": h}
                        break
                else:
                    # All rows full, go below the last one
                    max_y = 0
                    for c in components:
                        cl = c.get("layout", {})
                        max_y = max(max_y, cl.get("y", 0) + cl.get("h", 3))
                    layout = {"x": 0, "y": max_y, "w": w, "h": h}

            new_comp = {
                "id": comp_id,
                "type": comp_type,
                "title": tool_input.get("title", f"{comp_type}-{idx}"),
                "layout": layout,
                "datasource_id": tool_input.get("datasource_id", 1),
                "query_config": tool_input.get("query_config", {}),
                "chart_config": tool_input.get("chart_config", {}),
                "display_config": tool_input.get("display_config", {}),
            }
            components.append(new_comp)
            return {"ok": True, "component": new_comp, "message": f"已添加组件: {new_comp['title']}"}

        elif tool_name == "update_component":
            comp_id = tool_input["component_id"]
            target = next((c for c in components if c["id"] == comp_id), None)
            if not target:
                return {"ok": False, "error": f"组件 {comp_id} 不存在"}

            for field in ("title", "type", "datasource_id", "query_config", "chart_config", "display_config"):
                if field in tool_input and tool_input[field] is not None:
                    target[field] = tool_input[field]
            if "layout" in tool_input and tool_input["layout"]:
                target["layout"] = tool_input["layout"]
            return {"ok": True, "component": target, "message": f"已更新组件: {target.get('title', comp_id)}"}

        elif tool_name == "remove_component":
            comp_id = tool_input["component_id"]
            target = next((c for c in components if c["id"] == comp_id), None)
            if not target:
                return {"ok": False, "error": f"组件 {comp_id} 不存在"}
            components[:] = [c for c in components if c["id"] != comp_id]
            return {"ok": True, "message": f"已删除组件: {target.get('title', comp_id)}"}

        elif tool_name == "preview_query":
            ds_id = tool_input["datasource_id"]
            ds_configs = {d.get("id"): d for d in datasources}
            ds_config = ds_configs.get(ds_id)
            if not ds_config:
                return {"ok": False, "error": f"数据源 {ds_id} 不存在"}

            ds_type = ds_config.get("type", "")
            ds_cfg = ds_config.get("config", {})
            sql = tool_input.get("sql", "")
            try:
                if ds_type in ("mysql", "postgresql"):
                    rows = _execute_mysql_from_config(ds_cfg, sql)
                elif ds_type == "sqlite":
                    rows = _execute_sqlite_from_config(ds_cfg, sql)
                elif ds_type == "http_api":
                    rows = _execute_http_from_config(ds_cfg, {"sql": sql} if sql else {})
                else:
                    return {"ok": False, "error": f"不支持的数据源类型: {ds_type}"}

                preview = rows[:5]
                columns = list(preview[0].keys()) if preview else []
                return {
                    "ok": True, "row_count": len(rows), "preview_rows": preview,
                    "columns": columns, "message": f"查询成功，共 {len(rows)} 行，预览前 {len(preview)} 行"
                }
            except Exception as e:
                return {"ok": False, "error": str(e), "message": f"查询失败: {str(e)}"}

        return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    def chat(self, message: str, dashboard_state: dict, datasources: list[dict]) -> Generator[str, None, None]:
        """Stream agent response as SSE events."""

        user_content = json.dumps({
            "user_message": message,
            "dashboard_state_summary": {
                "component_count": len(dashboard_state.get("components", [])),
                "components": [
                    {"id": c["id"], "type": c.get("type", ""), "title": c.get("title", "")}
                    for c in dashboard_state.get("components", [])
                ]
            },
            "datasources_summary": [
                {"id": d["id"], "name": d.get("name", ""), "type": d.get("type", "")}
                for d in datasources
            ]
        }, ensure_ascii=False, indent=2)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]

        try:
            while True:
                yield self._sse_event("thinking", {"message": "正在思考..."})

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    stream=False,  # non-streaming for tool-use simplicity
                )

                choice = response.choices[0]
                msg = choice.message

                # Stream text content
                if msg.content:
                    yield self._sse_event("delta", {"text": msg.content})

                if not msg.tool_calls:
                    break

                # Append assistant message
                assistant_msg = {"role": "assistant", "content": msg.content or ""}
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in msg.tool_calls
                ]
                messages.append(assistant_msg)

                # Execute tools
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    try:
                        tool_input = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        tool_input = {}

                    yield self._sse_event("tool_call", {"tool": tool_name, "input": tool_input})

                    result = self._execute_tool(tool_name, tool_input, dashboard_state, datasources)

                    yield self._sse_event("tool_result", {"tool": tool_name, "result": result})

                    # Notify frontend of component changes
                    if tool_name == "add_component" and result.get("ok"):
                        yield self._sse_event("component", result["component"])
                    elif tool_name == "update_component" and result.get("ok"):
                        yield self._sse_event("component", result["component"])
                    elif tool_name == "remove_component" and result.get("ok"):
                        yield self._sse_event("remove_component", {"component_id": tool_input["component_id"]})

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str)
                    })

            yield self._sse_event("done", {"message": "已完成"})

        except Exception as e:
            logger.error("Agent error: %s", e)
            yield self._sse_event("error", {"message": str(e)})
