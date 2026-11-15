"""Gen 3 Voice & Agent REST surface."""

from __future__ import annotations

import base64
from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from megmis.common.auth import TenantContext, get_tenant, require_scope
from megmis.common.errors import AppError
from megmis.engines.voice import VoiceAgentService

router = APIRouter(prefix="/agents", tags=["agents"])
_agent = VoiceAgentService()


class CreateSession(BaseModel):
    lang: str = "en"
    channel: str = "ws"
    scenario: str | None = None


class UtteranceBody(BaseModel):
    text: str
    lang: str = "en"
    synthesize: bool = True


class TrainScoreBody(BaseModel):
    lang: str = "en"
    prompt_text: str
    expected_intent: str | None = None
    transcript: str
    audio_path: str | None = None


class WebRTCSignal(BaseModel):
    session_id: str
    type: str = Field(description="offer | answer | ice")
    sdp: str | None = None
    candidate: dict[str, Any] | None = None


# In-memory WebRTC signaling room (single-process Gen 3 MVP)
_SIGNAL_ROOMS: dict[str, list[dict[str, Any]]] = {}


@router.post("/sessions", status_code=201)
async def create_session(body: CreateSession, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    return {
        "data": _agent.create_session(
            str(tenant.tenant_id),
            lang=body.lang,
            channel=body.channel,
            scenario=body.scenario,
        )
    }


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    data = _agent.get_session(str(tenant.tenant_id), session_id)
    if not data:
        raise AppError("NOT_FOUND", "Session not found", status_code=404)
    return {"data": data}


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    return {"data": _agent.end_session(str(tenant.tenant_id), session_id)}


@router.post("/sessions/{session_id}/utterance")
async def text_utterance(
    session_id: str, body: UtteranceBody, tenant: TenantContext = Depends(get_tenant)
):
    require_scope(tenant, "agent:use")
    if not _agent.get_session(str(tenant.tenant_id), session_id):
        raise AppError("NOT_FOUND", "Session not found", status_code=404)
    return {
        "data": _agent.handle_utterance(
            str(tenant.tenant_id),
            session_id,
            body.text,
            lang=body.lang,
            synthesize=body.synthesize,
        )
    }


@router.post("/sessions/{session_id}/stt")
async def stt_upload(
    session_id: str,
    tenant: TenantContext = Depends(get_tenant),
    audio: UploadFile = File(...),
    lang: str = Form("en"),
    synthesize: bool = Form(True),
    run_agent: bool = Form(True),
):
    require_scope(tenant, "agent:use")
    if not _agent.get_session(str(tenant.tenant_id), session_id):
        raise AppError("NOT_FOUND", "Session not found", status_code=404)
    raw = await audio.read()
    mime = audio.content_type or "audio/webm"
    stt = _agent.transcribe(str(tenant.tenant_id), session_id, raw, lang=lang, mime=mime)
    result: dict[str, Any] = {"stt": stt}
    if run_agent and stt.get("text"):
        result["agent"] = _agent.handle_utterance(
            str(tenant.tenant_id),
            session_id,
            stt["text"],
            lang=lang,
            synthesize=synthesize,
        )
    return {"data": result}


@router.post("/sessions/{session_id}/tts")
async def tts_only(
    session_id: str,
    tenant: TenantContext = Depends(get_tenant),
    text: str = Form(...),
    lang: str = Form("en"),
):
    require_scope(tenant, "agent:use")
    if not _agent.get_session(str(tenant.tenant_id), session_id):
        raise AppError("NOT_FOUND", "Session not found", status_code=404)
    out = _agent.synthesize(str(tenant.tenant_id), session_id, text, lang=lang)
    audio = base64.b64decode(out["audio_b64"])
    return Response(content=audio, media_type=out.get("mime") or "audio/mpeg")


@router.post("/scenarios/mutare")
async def mutare_scenario(lang: str = "en", tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    return {"data": _agent.run_mutare_scenario(str(tenant.tenant_id), lang=lang)}


@router.get("/training/prompts")
async def training_prompts(lang: str = "en", tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    return {"data": {"lang": lang, "prompts": _agent.list_training_prompts(lang)}}


@router.post("/training/score")
async def training_score(body: TrainScoreBody, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    return {
        "data": _agent.score_training(
            str(tenant.tenant_id),
            lang=body.lang,
            prompt_text=body.prompt_text,
            expected_intent=body.expected_intent,
            transcript=body.transcript,
            audio_path=body.audio_path,
        )
    }


@router.post("/webrtc/signal")
async def webrtc_signal(body: WebRTCSignal, tenant: TenantContext = Depends(get_tenant)):
    """Lightweight WebRTC signaling exchange for Gen 3 browser peers."""
    require_scope(tenant, "agent:use")
    room = _SIGNAL_ROOMS.setdefault(body.session_id, [])
    msg = {
        "type": body.type,
        "sdp": body.sdp,
        "candidate": body.candidate,
        "tenant": tenant.slug,
    }
    room.append(msg)
    # return other messages (naive poll)
    others = [m for m in room if m is not msg][-10:]
    return {"data": {"queued": True, "peers": others}}


@router.get("/webrtc/signal/{session_id}")
async def webrtc_poll(session_id: str, tenant: TenantContext = Depends(get_tenant)):
    require_scope(tenant, "agent:use")
    return {"data": {"messages": _SIGNAL_ROOMS.get(session_id, [])[-20:]}}
