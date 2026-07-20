"""WebSocket endpoint for real-time system metrics streaming."""
import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from app.core.security import decode_token
from app.services.metrics_service import collect_metrics

logger = logging.getLogger(__name__)


async def metrics_websocket_handler(websocket: WebSocket):
    """
    Accepts WebSocket at /api/ws/metrics.
    Streams system metrics every 3 seconds.
    """
    await websocket.accept()

    # Auth
    token = websocket.query_params.get("token")
    if not token:
        await websocket.send_text(json.dumps({"type": "error", "message": "Auth required"}))
        await websocket.close(code=1008)
        return

    try:
        decode_token(token)
    except Exception:
        await websocket.send_text(json.dumps({"type": "error", "message": "Invalid token"}))
        await websocket.close(code=1008)
        return

    try:
        while True:
            metrics = await collect_metrics()
            await websocket.send_text(json.dumps({
                "type": "metrics",
                "data": metrics,
            }, default=str))
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Metrics WebSocket error: %s", e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
