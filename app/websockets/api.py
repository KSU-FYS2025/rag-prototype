from app.websockets.routes.AI_audio_socket_handler import SampleAIAudioHandler
from app.websockets.routes.audio_socket_handler import AudioSocketHandler
from app.websockets.routes.navigation_websocket_handler import (
    NavigationWebsocketHandler,
)
from fastapi import APIRouter, WebSocket
import logging
from pathlib import Path

from starlette.responses import HTMLResponse


class _DropLiveBlobLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage() != "Sending LLM Blob."


# Shows when ADK receives and releases buffered live tool calls
# ("Received tool call", "Returning aggregated tool_call_parts").
_live_logger = logging.getLogger("google_adk.google.adk.models.gemini_llm_connection")
_live_logger.setLevel(logging.DEBUG)
_live_logger.addFilter(_DropLiveBlobLogs())


router = APIRouter()

STATIC_DIR = Path(__file__).parent / "static"


@router.get("/audio/test")
async def index():
    html = (STATIC_DIR / "index.html").read_text()
    return HTMLResponse(html)


@router.websocket("/ws/AI")
async def ai_websocket(websocket: WebSocket, user_id: str, session_id: str):
    handler = NavigationWebsocketHandler(websocket, user_id, session_id)
    await handler.handle_loop()


@router.websocket("/ws/audio")
async def audio_loopback_websocket(websocket: WebSocket):
    handler = AudioSocketHandler(websocket)
    await handler.handle()


@router.websocket("/ws/AI/live")
async def live_ai_websocket(websocket: WebSocket):
    handler = SampleAIAudioHandler(websocket)
    await handler.handle()


# router.add_api_websocket_route("/ws/AI", websocket_route(NavigationWebsocketHandler))
# router.add_api_websocket_route("/ws/audio", websocket_route(AudioSocketHandler))
