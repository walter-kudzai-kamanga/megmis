"""WebSocket channel for Gen 3 voice agent sessions."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from megmis.common.auth import hash_api_key, lookup_api_key
from megmis.engines.voice import VoiceAgentService

router = APIRouter(tags=["voice-ws"])
_agent = VoiceAgentService()


@router.websocket("/ws/voice/{session_id}")
async def voice_socket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    api_key = websocket.query_params.get("api_key") or websocket.headers.get("x-api-key")
    if not api_key:
        await websocket.send_json({"error": "missing_api_key"})
        await websocket.close(code=4401)
        return
    ctx = lookup_api_key(hash_api_key(api_key))
    if ctx is None:
        await websocket.send_json({"error": "unauthorized"})
        await websocket.close(code=4401)
        return
    if "agent:use" not in ctx.scopes and "*" not in ctx.scopes:
        await websocket.send_json({"error": "forbidden"})
        await websocket.close(code=4403)
        return

    tenant_id = str(ctx.tenant_id)
    sess = _agent.get_session(tenant_id, session_id)
    if not sess:
        await websocket.send_json({"error": "session_not_found"})
        await websocket.close(code=4404)
        return

    await websocket.send_json(
        {
            "type": "ready",
            "session_id": session_id,
            "lang": sess.get("lang", "en"),
            "greeting": sess.get("meta", {}).get("greeting")
            or "Mamiriro voice channel open.",
        }
    )

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            if "bytes" in message and message["bytes"] is not None:
                lang = websocket.query_params.get("lang") or sess.get("lang") or "en"
                stt = _agent.transcribe(
                    tenant_id, session_id, message["bytes"], lang=lang, mime="audio/webm"
                )
                await websocket.send_json({"type": "stt", "data": stt})
                if stt.get("text"):
                    out = _agent.handle_utterance(
                        tenant_id, session_id, stt["text"], lang=lang, synthesize=True
                    )
                    await websocket.send_json({"type": "agent", "data": _strip_audio_for_ws(out)})
                continue

            raw = message.get("text")
            if not raw:
                continue
            try:
                payload: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "invalid_json"})
                continue

            typ = payload.get("type")
            lang = payload.get("lang") or sess.get("lang") or "en"
            if typ == "utterance":
                out = _agent.handle_utterance(
                    tenant_id,
                    session_id,
                    payload.get("text", ""),
                    lang=lang,
                    synthesize=bool(payload.get("synthesize", True)),
                )
                await websocket.send_json({"type": "agent", "data": _strip_audio_for_ws(out)})
            elif typ == "ping":
                await websocket.send_json({"type": "pong"})
            elif typ == "end":
                _agent.end_session(tenant_id, session_id)
                await websocket.send_json({"type": "ended"})
                break
            else:
                await websocket.send_json({"error": "unknown_type", "type": typ})
    except WebSocketDisconnect:
        return


def _strip_audio_for_ws(out: dict[str, Any]) -> dict[str, Any]:
    """Keep audio_b64 but drop huge nested blobs if needed — keep for UI playback."""
    return out
