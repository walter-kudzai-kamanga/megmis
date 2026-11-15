from __future__ import annotations

import pytest


def test_intent_detection_multilingual():
    from megmis.engines.voice.agent import detect_intent, extract_od, extract_places

    assert detect_intent("Plan the safest route from Harare to Mutare") == "route.plan"
    assert detect_intent("Ndafanira kuenda kuMutare nenzira yakachengeteka") == "route.plan"
    assert detect_intent("Ngicela indlela ephephile ukuya eMutare") == "route.plan"
    assert detect_intent("Start monitoring my journey") == "journey.monitor"
    assert detect_intent("Mamiriro emamiriro ari sei kuMutare") == "weather.current"
    assert extract_od("route from Bulawayo to Gweru")[:2] == ("Bulawayo", "Gweru")
    places = extract_places("weather in Victoria Falls")
    assert "Victoria Falls" in places
    o, d, unresolved = extract_od("route from harare to nyamaropa in nyanga zimbabwe")
    assert o == "Harare"
    assert d == "Nyamaropa"
    assert unresolved == []
    o2, d2, u2 = extract_od("route from harare to somewherefakeville")
    assert o2 == "Harare"
    assert d2 == "Somewherefakeville"  # free-text kept; Nominatim resolves at route time
    assert u2 == []
    o3, d3, _ = extract_od("harare to nyamaropa")
    assert o3 == "Harare" and d3 == "Nyamaropa"


def test_i18n_localize():
    from megmis.engines.voice.i18n import localize, training_prompts

    en = localize("greeting", "en")
    sn = localize("greeting", "sn")
    nd = localize("greeting", "nd")
    assert "Mamiriro" in en
    assert sn != en and nd != en
    assert len(training_prompts("sn")) >= 3


def test_mock_speech_roundtrip():
    from megmis.providers.mock_speech import MockSpeechProvider

    p = MockSpeechProvider()
    stt = p.stt(b"\x00" * 100, lang="en")
    assert "Bulawayo" in stt["text"] or "Gweru" in stt["text"]
    tts = p.tts("Hello Mutare", lang="en")
    assert tts["audio_bytes"] and tts["mime"] == "audio/wav"


def test_speech_factory_defaults_to_usable_provider(monkeypatch):
    from megmis.config import get_settings
    from megmis.providers.factory import get_speech_provider
    from megmis.providers.orchestrator import reset_orchestrator

    monkeypatch.setenv("SPEECH_PROVIDER", "mock")
    get_settings.cache_clear()
    reset_orchestrator()
    p = get_speech_provider()
    assert p.stt(b"abc", lang="nd")["lang"] == "nd"
    get_settings.cache_clear()
    reset_orchestrator()


@pytest.mark.integration
def test_mutare_voice_scenario(client, headers_a, monkeypatch):
    monkeypatch.setenv("SPEECH_PROVIDER", "mock")
    from megmis.config import get_settings
    from megmis.providers.orchestrator import reset_orchestrator

    get_settings.cache_clear()
    reset_orchestrator()

    r = client.post("/api/v1/agents/scenarios/mutare?lang=en", headers=headers_a)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["scenario"] == "mutare"
    assert data["passed"] is True
    assert len(data["steps"]) == 3
    tools = [t for s in data["steps"] for t in s.get("tool_trace", [])]
    names = {t.get("tool") for t in tools}
    assert "optimize_route" in names
    assert "journey.monitor" in names


@pytest.mark.integration
def test_voice_session_utterance_and_training(client, headers_a, monkeypatch):
    monkeypatch.setenv("SPEECH_PROVIDER", "mock")
    from megmis.config import get_settings
    from megmis.providers.factory import get_speech_provider

    get_settings.cache_clear()
    get_speech_provider.cache_clear()

    created = client.post(
        "/api/v1/agents/sessions",
        headers=headers_a,
        json={"lang": "en", "scenario": "mutare"},
    )
    assert created.status_code == 201
    sid = created.json()["data"]["session_id"]

    utt = client.post(
        f"/api/v1/agents/sessions/{sid}/utterance",
        headers=headers_a,
        json={"text": "Plan the safest route from Harare to Mutare", "lang": "en"},
    )
    assert utt.status_code == 200
    body = utt.json()["data"]
    assert body["intent"] == "route.plan"
    assert body["reply_text"]
    assert body["tool_trace"]
    assert body["results"]["understood"]["origin"] == "Harare"
    assert body["results"]["understood"]["destination"] == "Mutare"
    assert body["results"].get("ranked_routes") or body["results"].get("route")

    other = client.post(
        f"/api/v1/agents/sessions/{sid}/utterance",
        headers=headers_a,
        json={"text": "fastest route from Bulawayo to Gweru", "lang": "en", "synthesize": False},
    )
    assert other.status_code == 200
    ob = other.json()["data"]
    assert ob["results"]["understood"]["origin"] == "Bulawayo"
    assert ob["results"]["understood"]["destination"] == "Gweru"
    assert ob["results"]["understood"]["profile"] == "fastest"

    prompts = client.get("/api/v1/agents/training/prompts?lang=sn", headers=headers_a)
    assert prompts.status_code == 200
    assert prompts.json()["data"]["prompts"]

    scored = client.post(
        "/api/v1/agents/training/score",
        headers=headers_a,
        json={
            "lang": "en",
            "prompt_text": "Plan the safest route from Harare to Mutare",
            "expected_intent": "route.safest",
            "transcript": "Plan the safest route from Harare to Mutare",
        },
    )
    assert scored.status_code == 200
    assert scored.json()["data"]["score"] >= 0.9


def test_voice_lab_static_mounted(client):
    r = client.get("/voice/")
    # StaticFiles may 200 HTML or redirect; accept both
    assert r.status_code in {200, 307, 308}
    if r.status_code == 200:
        assert b"MAMIRI" in r.content or b"Mamiriro" in r.content
