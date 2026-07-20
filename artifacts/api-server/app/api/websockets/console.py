"""WebSocket endpoint for real-time bot console output."""
import asyncio
import json
import logging
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from app.services.bot_manager import bot_manager
from app.core.security import decode_token

logger = logging.getLogger(__name__)


async def console_websocket_handler(websocket: WebSocket):
    """
    Accepts WebSocket at /api/ws/console.
    Authenticates via token query param.
    Streams real-time log messages from the bot to the client.
    """
    await websocket.accept()

    # Authenticate via query param token
    token = websocket.query_params.get("token")
    if not token:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Authentication required"
        }))
        await websocket.close(code=1008)
        return

    try:
        decode_token(token)
    except Exception:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "Invalid token"
        }))
        await websocket.close(code=1008)
        return

    # Send welcome message
    await websocket.send_text(json.dumps({
        "type": "connected",
        "message": "Console connected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    # Send current bot status immediately
    await websocket.send_text(json.dumps({
        "type": "status",
        "data": bot_manager.get_status_dict(),
    }))

    # Register callback with bot manager
    queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    async def on_message(msg: dict):
        try:
            await queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass  # Drop if queue full to avoid blocking

    bot_manager.add_console_callback(on_message)

    try:
        # Send queued messages to client, and handle pings from client
        async def send_loop():
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                    await websocket.send_text(json.dumps(msg, default=str))
                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    await websocket.send_text(json.dumps({
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))
                except Exception:
                    break

        async def receive_loop():
            while True:
                try:
                    data = await websocket.receive_text()
                    # Handle pong or client commands
                    try:
                        msg = json.loads(data)
                        if msg.get("type") == "pong":
                            pass  # Keepalive acknowledged
                    except json.JSONDecodeError:
                        pass
                except WebSocketDisconnect:
                    break
                except Exception:
                    break

        await asyncio.gather(send_loop(), receive_loop())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Console WebSocket error: %s", e)
    finally:
        bot_manager.remove_console_callback(on_message)
        try:
            await websocket.close()
        except Exception:
            pass
