"""Voice & Agent Intelligence — interactive tool orchestration over real engines."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from megmis.common.schemas import LocationInput
from megmis.common.zimbabwe import (
    KNOWN_PLACES,
    canon_place_name,
    display_name,
    place_keys_longest_first,
)
from megmis.config import get_settings
from megmis.db.models import AgentSession, AudioArtefact, VoiceTrainingUtterance
from megmis.db.session import session_scope
from megmis.engines.risk.service import RiskService
from megmis.engines.road.service import RoadService
from megmis.engines.routing.service import RoutingService
from megmis.engines.voice.i18n import localize, training_prompts
from megmis.engines.weather.service import WeatherService
from megmis.providers.factory import get_speech_provider

# Canonical display names for known places (longest match first)
_PLACE_NAMES = sorted(
    {display_name(k) for k in KNOWN_PLACES},
    key=len,
    reverse=True,
)
_PLACE_KEYS = place_keys_longest_first()


def _wer(ref: str, hyp: str) -> float:
    r = ref.lower().split()
    h = hyp.lower().split()
    if not r:
        return 0.0 if not h else 1.0
    dp = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        dp[i][0] = i
    for j in range(len(h) + 1):
        dp[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            cost = 0 if r[i - 1] == h[j - 1] else 1
            dp[i][j] = min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost)
    return round(dp[-1][-1] / len(r), 3)


def _canon_place(raw: str) -> str | None:
    return canon_place_name(raw)


def extract_places(text: str) -> list[str]:
    """Find known Zimbabwe places mentioned in utterance (order of appearance)."""
    t = text.lower()
    found: list[tuple[int, str]] = []
    used_spans: list[tuple[int, int]] = []
    for key in _PLACE_KEYS:
        if len(key) < 3:
            continue
        start = 0
        while True:
            idx = t.find(key, start)
            if idx < 0:
                break
            end = idx + len(key)
            if any(not (end <= a or idx >= b) for a, b in used_spans):
                start = idx + 1
                continue
            used_spans.append((idx, end))
            found.append((idx, display_name(key)))
            start = end
    found.sort(key=lambda x: x[0])
    out: list[str] = []
    for _, name in found:
        if name not in out:
            out.append(name)
    return out


def extract_raw_od_phrases(text: str) -> tuple[str | None, str | None]:
    """Pull raw from/to phrases even when places are unknown to the gazetteer."""
    t = text.strip()
    m = re.search(
        r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:\?|$|\.|!)",
        t,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(" .,!"), m.group(2).strip(" .,!")
    m = re.search(
        r"\bfrom\s+([a-zA-Z][a-zA-Z0-9\s,'-]{1,50}?)\s+to\s+([a-zA-Z][a-zA-Z0-9\s,'-]{1,60})",
        t,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(" .,!"), m.group(2).strip(" .,!")
    m = re.search(
        r"\broute\s+(?:from\s+)?(.+?)\s+to\s+(.+?)(?:\?|$|\.|!)",
        t,
        flags=re.I,
    )
    if m:
        return m.group(1).strip(" .,!"), m.group(2).strip(" .,!")
    return None, None


def extract_od(
    text: str, memory: dict[str, Any] | None = None
) -> tuple[str | None, str | None, list[str]]:
    """
    Resolve origin/destination from free text.
    Returns (origin, destination, unresolved_phrases).
    Never invents a second place when only one was understood.
    """
    memory = memory or {}
    low = text.strip().lower()
    unresolved: list[str] = []

    raw_o, raw_d = extract_raw_od_phrases(text)
    if raw_o or raw_d:
        o = _canon_place(raw_o) if raw_o else None
        d = _canon_place(raw_d) if raw_d else None
        if raw_o and not o:
            unresolved.append(raw_o)
        if raw_d and not d:
            unresolved.append(raw_d)
        if o and d and o.lower() != d.lower():
            return o, d, unresolved
        if o and d and o.lower() == d.lower():
            # same resolved name — treat dest as unresolved if raw differed
            if raw_d and raw_d.lower() != raw_o.lower():
                unresolved.append(raw_d)
                return o, None, unresolved
        if o and not d:
            return o, None, unresolved
        if d and not o:
            mem_o = memory.get("origin")
            if mem_o and str(mem_o).lower() != d.lower():
                return str(mem_o), d, unresolved
            return None, d, unresolved

    # Shona-ish: kuenda kuX
    m = re.search(r"\bkuenda\s+ku([a-zA-Z]+)\b", low)
    if m:
        d = _canon_place(m.group(1))
        if not d:
            unresolved.append(m.group(1))
        o = memory.get("origin") or "Harare"
        if d and str(o).lower() != d.lower():
            return str(o), d, unresolved

    # Ndebele-ish: ukuya eX
    m = re.search(r"\bukuya\s+e([a-zA-Z]+)\b", low)
    if m:
        d = _canon_place(m.group(1))
        if not d:
            unresolved.append(m.group(1))
        o = memory.get("origin") or "Harare"
        if d and str(o).lower() != d.lower():
            return str(o), d, unresolved

    places = extract_places(text)
    # Drop duplicate same-name collapses
    places = list(dict.fromkeys(places))
    if len(places) >= 2:
        return places[0], places[1], unresolved
    if len(places) == 1:
        origin = memory.get("origin")
        if origin and places[0].lower() != str(origin).lower():
            return str(origin), places[0], unresolved
        dest = memory.get("destination")
        if dest and places[0].lower() != str(dest).lower():
            return places[0], str(dest), unresolved
        # Only one known place in the utterance — do not invent O→O
        if raw_d and not _canon_place(raw_d):
            unresolved.append(raw_d)
        return None, None, unresolved or ([places[0]] if not raw_d else unresolved)

    if memory.get("origin") and memory.get("destination"):
        mo, md = str(memory["origin"]), str(memory["destination"])
        if mo.lower() != md.lower():
            return mo, md, unresolved
    return None, None, unresolved


def extract_profile(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("fast", "quick", "shortest time")):
        return "fastest"
    if any(k in t for k in ("fuel", "eco", "efficient")):
        return "fuel"
    if any(k in t for k in ("cheap", "cost", "affordable")):
        return "cheapest"
    return "safest"


def detect_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ("monitor", "tarisa", "qapha", "tracking", "track my")):
        return "journey.monitor"
    if any(k in t for k in ("weather", "forecast", "temperature", "mamiriro emamiriro", "simo sezulu")):
        return "weather.current"
    if any(k in t for k in ("incident", "pothole", "closure", "zviitiko", "ingozi")):
        return "road.incidents"
    if any(k in t for k in ("risk", "njodzi", "ingozi yohambo", "how safe")):
        return "journey.risk"
    if any(
        k in t
        for k in (
            "route",
            "directions",
            "navigate",
            "drive",
            "nzira",
            "indlela",
            "from ",
            " to ",
            "safest",
            "fastest",
            "kuenda",
        )
    ):
        return "route.plan"
    if any(k in t for k in ("speak", "taura", "khuluma", "say the", "read the route")):
        return "route.speak"
    # place names alone → treat as weather ask for that place if one, else route if two
    places = extract_places(text)
    if len(places) >= 2:
        return "route.plan"
    if len(places) == 1:
        return "weather.current"
    return "general"


class VoiceAgentService:
    """Independent Voice module (ADR-009) — interactive over real engines."""

    def __init__(self) -> None:
        self.weather = WeatherService()
        self.routing = RoutingService()
        self.road = RoadService()
        self.risk = RiskService()
        self.speech = get_speech_provider()

    def _load_memory(self, tenant_id: str, session_id: str) -> dict[str, Any]:
        with session_scope(tenant_id=tenant_id) as session:
            row = session.get(AgentSession, UUID(session_id))
            if not row:
                return {}
            meta = dict(row.meta or {})
            return dict(meta.get("memory") or {})

    def _save_memory(self, tenant_id: str, session_id: str, memory: dict[str, Any], turn: dict) -> None:
        with session_scope(tenant_id=tenant_id) as session:
            row = session.get(AgentSession, UUID(session_id))
            if not row:
                return
            meta = dict(row.meta or {})
            meta["memory"] = memory
            turns = list(meta.get("turns") or [])
            turns.append(turn)
            meta["turns"] = turns[-40:]
            meta["last_intent"] = turn.get("intent")
            row.meta = meta
            row.lang = turn.get("lang") or row.lang

    def create_session(
        self,
        tenant_id: str,
        *,
        lang: str = "en",
        channel: str = "ws",
        scenario: str | None = None,
    ) -> dict[str, Any]:
        sid = uuid4()
        greeting = localize(
            "mutare_ready" if scenario == "mutare" else "greeting",
            lang,
        )
        with session_scope(tenant_id=tenant_id) as session:
            session.add(
                AgentSession(
                    id=sid,
                    tenant_id=UUID(tenant_id),
                    channel=channel,
                    state="active",
                    lang=lang,
                    scenario=scenario,
                    meta={
                        "turns": [],
                        "greeting": greeting,
                        "memory": {"origin": None, "destination": None, "profile": "safest"},
                    },
                )
            )
        return {
            "session_id": str(sid),
            "lang": lang,
            "channel": channel,
            "scenario": scenario,
            "greeting": greeting,
            "state": "active",
            "places": _PLACE_NAMES,
        }

    def get_session(self, tenant_id: str, session_id: str) -> dict[str, Any] | None:
        with session_scope(tenant_id=tenant_id) as session:
            row = session.get(AgentSession, UUID(session_id))
            if row is None or str(row.tenant_id) != tenant_id:
                return None
            return {
                "session_id": str(row.id),
                "lang": row.lang,
                "channel": row.channel,
                "scenario": row.scenario,
                "state": row.state,
                "meta": row.meta or {},
                "started_at": row.started_at.isoformat() if row.started_at else None,
            }

    def end_session(self, tenant_id: str, session_id: str) -> dict[str, Any]:
        with session_scope(tenant_id=tenant_id) as session:
            row = session.get(AgentSession, UUID(session_id))
            if row is None:
                return {"ended": False}
            row.state = "ended"
            row.ended_at = datetime.now(UTC)
            return {"ended": True, "session_id": session_id}

    def _save_audio(
        self,
        tenant_id: str,
        session_id: str,
        kind: str,
        data: bytes,
        *,
        lang: str,
        ext: str,
        meta: dict | None = None,
    ) -> str:
        settings = get_settings()
        base = Path(settings.voice_audio_dir) / tenant_id / session_id
        base.mkdir(parents=True, exist_ok=True)
        name = f"{kind}_{uuid4().hex[:10]}.{ext}"
        path = base / name
        path.write_bytes(data)
        with session_scope(tenant_id=tenant_id) as session:
            session.add(
                AudioArtefact(
                    tenant_id=UUID(tenant_id),
                    session_id=UUID(session_id),
                    kind=kind,
                    path=str(path),
                    lang=lang,
                    meta=meta or {},
                )
            )
        return str(path)

    def transcribe(
        self, tenant_id: str, session_id: str, audio: bytes, *, lang: str, mime: str
    ) -> dict[str, Any]:
        result = self.speech.stt(audio, lang=lang, mime=mime)
        ext = "webm" if "webm" in mime else "wav"
        path = self._save_audio(
            tenant_id, session_id, "stt_in", audio, lang=lang, ext=ext, meta=result
        )
        result["audio_path"] = path
        return result

    def synthesize(
        self, tenant_id: str, session_id: str, text: str, *, lang: str
    ) -> dict[str, Any]:
        result = self.speech.tts(text, lang=lang)
        audio = result.pop("audio_bytes")
        ext = "mp3" if "mpeg" in result.get("mime", "") else "wav"
        path = self._save_audio(
            tenant_id, session_id, "tts_out", audio, lang=lang, ext=ext, meta={"text": text}
        )
        result["audio_path"] = path
        result["audio_b64"] = __import__("base64").b64encode(audio).decode()
        return result

    def _tool_route(
        self,
        tenant_id: str,
        lang: str,
        origin: str,
        destination: str,
        profile: str = "safest",
    ) -> dict[str, Any]:
        route_env = self.routing.optimize(
            LocationInput(name=origin),
            LocationInput(name=destination),
            profile=profile,
            tenant_id=tenant_id,
        )
        data = route_env.data or {}
        routes = data.get("routes") or []
        route_id = data.get("route_id") or data.get("id")
        ranked = []
        for i, r in enumerate(routes):
            ranked.append(
                {
                    "rank": i + 1,
                    "label": r.get("label") or f"Route {i+1}",
                    "distance_m": r.get("distance_m") or r.get("distance") or 0,
                    "duration_s": r.get("duration_s") or r.get("duration") or 0,
                    "explanation": r.get("explanation") or "",
                    "hazards": r.get("hazards") or [],
                    "cost_breakdown": r.get("cost_breakdown") or r.get("costs") or {},
                    "geometry": r.get("geometry") or [],
                    "node_path": r.get("node_path") or [],
                    "algorithm": r.get("algorithm") or "dijkstra",
                    "via": r.get("via"),
                }
            )
        if not ranked:
            ranked = [
                {
                    "rank": 1,
                    "label": f"{origin} → {destination} ({profile})",
                    "distance_m": 0,
                    "duration_s": 0,
                    "explanation": "No scored candidates returned by routing provider",
                    "hazards": [],
                }
            ]
        top = ranked[0]
        km = round((top["distance_m"] or 0) / 1000, 1)
        minutes = max(1, round((top["duration_s"] or 0) / 60)) if top["duration_s"] else 0
        spoken = [
            localize(
                "route_intro",
                lang,
                n=len(ranked),
                origin=origin,
                destination=destination,
            ),
            localize(
                "top_route",
                lang,
                label=top["label"],
                km=km,
                minutes=minutes or "?",
                why=top["explanation"] or "",
            ),
        ]
        origin_ll = (data.get("origin") or {})
        dest_ll = (data.get("destination") or {})
        return {
            "tool": "optimize_route",
            "origin": origin,
            "destination": destination,
            "profile": profile,
            "route_id": route_id,
            "ranked_routes": ranked,
            "algorithm": "dijkstra",
            "map": {
                "origin": {
                    "name": origin,
                    "lat": origin_ll.get("lat"),
                    "lon": origin_ll.get("lon"),
                },
                "destination": {
                    "name": destination,
                    "lat": dest_ll.get("lat"),
                    "lon": dest_ll.get("lon"),
                },
                "routes": [
                    {
                        "rank": r["rank"],
                        "label": r["label"],
                        "geometry": r.get("geometry") or [],
                        "distance_m": r["distance_m"],
                        "duration_s": r["duration_s"],
                    }
                    for r in ranked
                ],
            },
            "spoken_parts": spoken,
            "result_summary": {
                "from": origin,
                "to": destination,
                "profile": profile,
                "top_label": top["label"],
                "km": km,
                "minutes": minutes,
                "alternatives": len(ranked),
                "algorithm": "dijkstra",
                "via": top.get("via"),
            },
        }

    def _tool_weather(self, lang: str, place: str) -> dict[str, Any]:
        w = self.weather.current(LocationInput(name=place))
        data = w.data or {}
        spoken = localize(
            "weather",
            lang,
            condition=data.get("condition", "clear"),
            temp=data.get("temperature_c", "?"),
        )
        # include place name in spoken line
        spoken = f"{place}: {spoken}"
        return {
            "tool": "get_current_weather",
            "place": place,
            "weather": data,
            "spoken_parts": [spoken],
            "result_summary": {
                "place": place,
                "condition": data.get("condition"),
                "temperature_c": data.get("temperature_c"),
                "humidity": data.get("humidity"),
                "wind": data.get("wind"),
            },
        }

    def _tool_incidents(self, origin: str, destination: str) -> dict[str, Any]:
        corridor = f"{origin}-{destination}"
        inc = self.road.incidents(corridor=corridor)
        items = (inc.data or {}).get("incidents") or []
        return {
            "tool": "get_road_incidents",
            "corridor": corridor,
            "incidents": items,
            "spoken_parts": [f"{len(items)} active incidents on {corridor}."],
            "result_summary": {"corridor": corridor, "count": len(items), "incidents": items[:5]},
        }

    def _tool_risk(
        self, tenant_id: str, lang: str, origin: str, destination: str, profile: str
    ) -> dict[str, Any]:
        risk = self.risk.assess_journey(
            LocationInput(name=origin),
            LocationInput(name=destination),
            profile=profile,
            tenant_id=tenant_id,
            activity="road_trip",
        )
        d = risk.data or {}
        spoken = localize("risk", lang, level=d.get("level", "moderate"), score=d.get("score", 0.4))
        return {
            "tool": "assess_journey_risk",
            "origin": origin,
            "destination": destination,
            "risk": d,
            "spoken_parts": [spoken],
            "result_summary": {
                "from": origin,
                "to": destination,
                "level": d.get("level"),
                "score": d.get("score"),
                "assessment_id": d.get("assessment_id"),
                "recommendations": d.get("recommendations") or [],
            },
        }

    def _tool_monitor(
        self,
        tenant_id: str,
        lang: str,
        origin: str,
        destination: str,
        profile: str,
        route_id: str | None = None,
    ) -> dict[str, Any]:
        routed = None
        if not route_id:
            routed = self._tool_route(tenant_id, lang, origin, destination, profile)
            route_id = routed.get("route_id")
        journey_id = None
        status = "monitoring"
        if route_id:
            try:
                j = self.routing.create_journey(str(route_id), tenant_id)
                journey_id = (j.data or {}).get("id")
                status = (j.data or {}).get("status") or "active"
            except Exception:
                journey_id = str(uuid4())
        else:
            journey_id = str(uuid4())
        spoken = localize("monitor_start", lang)
        out = {
            "tool": "journey.monitor",
            "journey_id": journey_id,
            "route_id": route_id,
            "origin": origin,
            "destination": destination,
            "status": status,
            "spoken_parts": [spoken],
            "result_summary": {
                "journey_id": journey_id,
                "route_id": route_id,
                "from": origin,
                "to": destination,
                "status": status,
            },
        }
        if routed:
            out["ranked_routes"] = routed.get("ranked_routes")
            out["map"] = routed.get("map")
        return out

    def handle_utterance(
        self,
        tenant_id: str,
        session_id: str,
        text: str,
        *,
        lang: str = "en",
        synthesize: bool = True,
    ) -> dict[str, Any]:
        memory = self._load_memory(tenant_id, session_id)
        intent = detect_intent(text)
        profile = extract_profile(text)
        origin, destination, unresolved = extract_od(text, memory)
        places = extract_places(text)
        weather_place = places[-1] if places else (destination or memory.get("last_place") or "Harare")

        # update session memory when user names places — never invent O→O
        if origin and destination and origin.lower() != destination.lower():
            memory["origin"], memory["destination"] = origin, destination
        elif places:
            if len(places) >= 2 and places[0].lower() != places[1].lower():
                memory["origin"], memory["destination"] = places[0], places[1]
            elif len(places) == 1:
                memory["last_place"] = places[0]
        memory["profile"] = profile

        tool_trace: list[dict[str, Any]] = []
        spoken_parts: list[str] = []
        results: dict[str, Any] = {
            "understood": {
                "intent": intent,
                "origin": origin,
                "destination": destination,
                "profile": profile,
                "places": places,
                "unresolved": unresolved,
                "weather_place": weather_place,
            }
        }

        needs_od = intent in {
            "route.plan",
            "route.speak",
            "road.incidents",
            "journey.risk",
            "journey.monitor",
        }
        same_od = bool(origin and destination and origin.lower() == destination.lower())
        if needs_od and (not origin or not destination or same_od):
            bad = ", ".join(unresolved) if unresolved else "(could not parse destination)"
            hint = (
                f"I could not resolve that corridor. Unresolved: {bad}. "
                f"Try: 'route from Harare to Nyanga' or 'route from Bulawayo to Gweru'. "
                f"Known places include: {', '.join(_PLACE_NAMES[:10])}…"
            )
            spoken_parts.append(hint)
            results["help"] = {
                "known_places": _PLACE_NAMES,
                "need": "origin_and_destination",
                "unresolved": unresolved,
            }
        elif intent in {"route.plan", "route.speak"}:
            tr = self._tool_route(tenant_id, lang, str(origin), str(destination), profile)
            tool_trace.append(tr)
            spoken_parts.extend(tr["spoken_parts"])
            results["route"] = tr.get("result_summary")
            results["ranked_routes"] = tr.get("ranked_routes")
            results["map"] = tr.get("map")
            risk = self._tool_risk(tenant_id, lang, str(origin), str(destination), profile)
            tool_trace.append(risk)
            spoken_parts.extend(risk["spoken_parts"])
            results["risk"] = risk.get("result_summary")
            wx = self._tool_weather(lang, str(weather_place))
            tool_trace.append(wx)
            spoken_parts.extend(wx["spoken_parts"])
            results["weather"] = wx.get("result_summary")
        elif intent == "weather.current":
            wx = self._tool_weather(lang, str(weather_place))
            tool_trace.append(wx)
            spoken_parts.extend(wx["spoken_parts"])
            results["weather"] = wx.get("result_summary")
        elif intent == "road.incidents":
            inc = self._tool_incidents(str(origin), str(destination))
            tool_trace.append(inc)
            spoken_parts.extend(inc["spoken_parts"])
            results["incidents"] = inc.get("result_summary")
        elif intent == "journey.risk":
            risk = self._tool_risk(tenant_id, lang, str(origin), str(destination), profile)
            tool_trace.append(risk)
            spoken_parts.extend(risk["spoken_parts"])
            results["risk"] = risk.get("result_summary")
        elif intent == "journey.monitor":
            mon = self._tool_monitor(tenant_id, lang, str(origin), str(destination), profile)
            tool_trace.append(mon)
            spoken_parts.extend(mon["spoken_parts"])
            results["journey"] = mon.get("result_summary")
            if mon.get("ranked_routes"):
                results["ranked_routes"] = mon["ranked_routes"]
            if mon.get("map"):
                results["map"] = mon["map"]
        else:
            hint = (
                f"I heard: {text[:120]}. Try: 'route from Bulawayo to Gweru', "
                f"'weather in Victoria Falls', or 'monitor my journey to Masvingo'. "
                f"Known places: {', '.join(_PLACE_NAMES[:6])}…"
            )
            spoken_parts.append(hint)
            results["help"] = {"known_places": _PLACE_NAMES}

        reply = " ".join(spoken_parts)
        audio_payload = None
        if synthesize:
            try:
                audio_payload = self.synthesize(tenant_id, session_id, reply, lang=lang)
            except Exception as exc:  # noqa: BLE001
                audio_payload = {
                    "error": str(exc),
                    "mime": None,
                    "audio_b64": None,
                    "lang": lang,
                }

        turn = {
            "at": datetime.now(UTC).isoformat(),
            "user": text,
            "intent": intent,
            "reply": reply,
            "lang": lang,
            "tools": [t.get("tool") for t in tool_trace],
            "understood": results.get("understood"),
        }
        self._save_memory(tenant_id, session_id, memory, turn)

        return {
            "session_id": session_id,
            "intent": intent,
            "user_text": text,
            "reply_text": reply,
            "lang": lang,
            "tool_trace": tool_trace,
            "results": results,
            "audio": audio_payload,
            "turn": turn,
        }

    def run_mutare_scenario(self, tenant_id: str, *, lang: str = "en") -> dict[str, Any]:
        sess = self.create_session(tenant_id, lang=lang, channel="scenario", scenario="mutare")
        sid = sess["session_id"]
        script = [
            "Plan the safest route from Harare to Mutare",
            "What is the weather in Mutare",
            "Start monitoring my journey to Mutare",
        ]
        if lang == "sn":
            script = [
                "Ndafanira kuenda kuMutare nenzira yakachengeteka",
                "Mamiriro emamiriro ari sei kuMutare",
                "Tanga kutarisa rwendo rwangu kuMutare",
            ]
        elif lang == "nd":
            script = [
                "Ngicela indlela ephephile ukuya eMutare",
                "Simo sezulu sinjani eMutare manje",
                "Qala ukuqapha uhambo lwami eMutare",
            ]
        steps = []
        for line in script:
            steps.append(self.handle_utterance(tenant_id, sid, line, lang=lang, synthesize=True))
        return {
            "scenario": "mutare",
            "session": sess,
            "steps": steps,
            "passed": all(
                s["intent"]
                in {"route.plan", "route.speak", "weather.current", "journey.monitor", "journey.risk"}
                for s in steps
            ),
        }

    def list_training_prompts(self, lang: str = "en") -> list[dict[str, str]]:
        return training_prompts(lang)

    def score_training(
        self,
        tenant_id: str,
        *,
        lang: str,
        prompt_text: str,
        expected_intent: str | None,
        transcript: str,
        audio_path: str | None = None,
    ) -> dict[str, Any]:
        wer = _wer(prompt_text, transcript)
        intent = detect_intent(transcript)
        # map legacy training intents
        legacy = {
            "route.safest": "route.plan",
            "route.speak": "route.plan",
        }
        intent_norm = legacy.get(intent, intent)
        expected_norm = legacy.get(expected_intent or "", expected_intent)
        intent_ok = (expected_norm is None) or intent_norm == expected_norm or intent == expected_intent
        score = max(0.0, round((1.0 - wer) * (1.0 if intent_ok else 0.7), 3))
        with session_scope(tenant_id=tenant_id) as session:
            row = VoiceTrainingUtterance(
                tenant_id=UUID(tenant_id),
                lang=lang,
                prompt_text=prompt_text,
                expected_intent=expected_intent,
                transcript=transcript,
                wer=wer,
                audio_path=audio_path,
                score=score,
                meta={"intent": intent, "intent_ok": intent_ok},
            )
            session.add(row)
            session.flush()
            uid = str(row.id)
        return {
            "id": uid,
            "wer": wer,
            "score": score,
            "intent": intent,
            "intent_ok": intent_ok,
            "transcript": transcript,
        }
