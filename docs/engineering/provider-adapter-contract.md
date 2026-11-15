# Provider Adapter Contract

Every provider implements a Protocol; engines depend only on the Protocol.

## WeatherProvider
get_current(lat, lon) -> WeatherSnapshot
get_forecast(lat, lon, days) -> [DailyForecast]
get_hourly(lat, lon, date) -> [HourlyForecast]
get_historical(lat, lon, start, end) -> [Observation]
get_alerts(lat, lon) -> [Alert]  # Alert.official flag required

## RoutingProvider
route(origin, dest, waypoints, costing_profile, departure_time) -> [RouteCandidate]
matrix(sources, targets, profile) -> Matrix
Build/refresh: out-of-band graph build job; health check endpoint.

## GeocodingProvider
geocode(address) -> [LatLon]
reverse(lat, lon) -> Address

## SpeechProvider
stt(audio_stream, lang) -> Transcript
tts(text, lang, voice) -> AudioStream

## Providers
- Open-Meteo: primary weather. FREE API IS NON-COMMERCIAL — resolve commercial
  licence before launch. Fallback: OpenWeather (paid tiers). Official warnings
  from national met services, flagged official=true.
- Valhalla: primary routing (A*, bidirectional A*, dynamic costing).
- GraphHopper: alternative routing (custom edge weights, priorities).
- OSRM: high-performance alternative.
- Google Routes: benchmark/fallback, traffic-aware.
- Speech: adapter only in Phase 1; concrete provider chosen in Phase 3.

## Error/retry
Adapters raise ProviderError(retryable, code). Orchestrator retries with backoff
and fails over to configured fallback provider. Health checks gate failover.