"""Agent chat endpoint — SSE streaming for the NL-to-Dashboard agent."""
import json
import logging
import traceback
from flask import Blueprint, request, jsonify, Response, g

from app.services.auth import login_required
from app.services.agent import DashboardAgent

logger = logging.getLogger(__name__)

agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")


@agent_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    """SSE endpoint for the chat agent.

    Expects JSON body:
      - message: user's natural-language input
      - dashboard_state: current canvas_json from the frontend
      - datasources: list of datasource dicts
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required"}), 400

    dashboard_state = data.get("dashboard_state") or {"components": []}
    datasources = data.get("datasources") or []

    try:
        agent = DashboardAgent()
    except ValueError as e:
        return jsonify({"error": str(e), "hint": "请设置 DEEPSEEK_API_KEY 环境变量"}), 503

    def generate():
        try:
            for sse_chunk in agent.chat(message, dashboard_state, datasources):
                yield sse_chunk
        except Exception as e:
            logger.error("Agent stream error: %s", traceback.format_exc())
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
