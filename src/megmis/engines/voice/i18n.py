"""Multilingual path EN → Shona (sn) / Ndebele (nd) for voice agent responses."""

from __future__ import annotations

# Curated phrase bank for Gen 3 voice (mobility domain). Not a full MT engine —
# agent replies are composed from templates + tool facts, then localized.
_PHRASES: dict[str, dict[str, str]] = {
    "greeting": {
        "en": "Mamiriro voice ready. How can I help your journey?",
        "sn": "Mamiriro izwi rakagadzirira. Ndingakubatsira sei parwendo rwako?",
        "nd": "IMamiriro ilizwi selilungile. Ngingakusiza kanjani ohambweni lwakho?",
    },
    "route_intro": {
        "en": "I found {n} ranked routes from {origin} to {destination}.",
        "sn": "Ndawana nzira {n} dzakakwiriridzwa kubva ku{origin} kuenda ku{destination}.",
        "nd": "Ngithole izindlela ezingu-{n} ezikhethiwe ukusuka e{origin} ukuya e{destination}.",
    },
    "top_route": {
        "en": "Top recommendation: {label}. Distance about {km} kilometres, taking roughly {minutes} minutes. {why}",
        "sn": "Yakanakisisa: {label}. Nhambwe inosvika makiromita {km}, inotora maminetsi {minutes}. {why}",
        "nd": "Okuhle kakhulu: {label}. Ibanga cishe amakhilomitha {km}, ithatha imizuzu engu-{minutes}. {why}",
    },
    "weather": {
        "en": "Weather along the corridor: {condition}, about {temp} degrees.",
        "sn": "Mamiriro emamiriro epasi: {condition}, anenge digiri {temp}.",
        "nd": "Isimo sezulu endleleni: {condition}, cishe amadigri angu-{temp}.",
    },
    "risk": {
        "en": "Journey risk level is {level} with score {score}.",
        "sn": "Njodzi yerwendo iri pa{level} nechikero {score}.",
        "nd": "Izinga lengozi yohambo ngu-{level} namaphuzu angu-{score}.",
    },
    "monitor_start": {
        "en": "I am now monitoring your journey. I will alert you if conditions change.",
        "sn": "Ndava kutarisa rwendo rwako. Ndichakuzivisa kana mamiriro achinja.",
        "nd": "Sengiqapha uhambo lwakho. Ngizokwazisa uma isimo sishintsha.",
    },
    "mutare_ready": {
        "en": "Mutare voice scenario ready. Ask me to plan the safest Harare to Mutare route.",
        "sn": "Chiitiko cheMutare chagadzirira. Ndibvunze kuti ndironge nzira yakachengeteka kubva kuHarare kuenda kuMutare.",
        "nd": "Isimo sezwi saseMutare silungile. Ngicela ungibuze ukuthi ngihlele indlela ephephile ukusuka eHarare ukuya eMutare.",
    },
    "fallback": {
        "en": "I heard: {heard}. Let me work on that.",
        "sn": "Ndanzwa: {heard}. Regai ndishande nazvo.",
        "nd": "Ngezwa: {heard}. Ake ngisebenze ngakho.",
    },
}


def localize(key: str, lang: str = "en", **kwargs: object) -> str:
    bank = _PHRASES.get(key) or _PHRASES["fallback"]
    template = bank.get(lang) or bank["en"]
    try:
        return template.format(**kwargs)
    except Exception:
        return template


def training_prompts(lang: str = "en") -> list[dict[str, str]]:
    """Utterances for the voice training lab."""
    prompts = {
        "en": [
            ("Route from Bulawayo to Gweru fastest", "route.plan"),
            ("Safest route from Harare to Masvingo", "route.plan"),
            ("What is the weather in Victoria Falls right now", "weather.current"),
            ("Start monitoring my journey to Masvingo", "journey.monitor"),
            ("Are there any road incidents from Harare to Bulawayo", "road.incidents"),
        ],
        "sn": [
            ("Nzira kubva kuHarare kuenda kuBulawayo", "route.plan"),
            ("Mamiriro emamiriro ari sei kuMutare", "weather.current"),
            ("Tanga kutarisa rwendo rwangu kuMasvingo", "journey.monitor"),
            ("Pane zviitiko zvemunzira paA3 here", "road.incidents"),
            ("Nzira yakachengeteka kubva kuGweru kuenda kuMutare", "route.plan"),
        ],
        "nd": [
            ("Indlela ukusuka eHarare ukuya eBulawayo", "route.plan"),
            ("Simo sezulu sinjani eVictoria Falls manje", "weather.current"),
            ("Qala ukuqapha uhambo lwami eMasvingo", "journey.monitor"),
            ("Kukhona yini izingozi emgwaqeni i-A5", "road.incidents"),
            ("Indlela ephephile ukusuka eGweru ukuya eMutare", "route.plan"),
        ],
    }
    rows = prompts.get(lang, prompts["en"])
    return [{"text": t, "intent": i, "lang": lang} for t, i in rows]
