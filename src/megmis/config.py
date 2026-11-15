from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://megmis:megmis@localhost:5433/megmis"
    redis_url: str = "redis://localhost:6379/0"
    use_persistence: bool = True  # USE_PERSISTENCE=false for pure unit tests

    weather_provider: str = "mock"
    routing_provider: str = "mock"
    geocode_provider: str = "mock"
    speech_provider: str = "whisper"  # whisper | mock
    whisper_model: str = "base"  # tiny|base|small|medium|large-v3
    whisper_device: str = "cpu"  # cpu|cuda
    whisper_compute_type: str = "int8"
    tts_provider: str = "edge"  # edge | mock
    voice_default_lang: str = "en"
    voice_audio_dir: str = "data/audio"
    voice_ui_enabled: bool = True

    open_meteo_base_url: str = "https://api.open-meteo.com"
    openweather_key: str = ""
    valhalla_url: str = ""
    graphhopper_url: str = ""
    osrm_url: str = "https://router.project-osrm.org"

    # RLS-enforced app role (Gen 2). When database_app_url is set, prefer it unless USE_APP_ROLE=false.
    database_app_url: str = (
        "postgresql+psycopg://megmis_app:megmis_app@localhost:5433/megmis"
    )
    use_app_role: bool = True

    mcp_transport: str = "http"
    console_upstream: str = "http://api:8000"  # used by optional console service
    console_port: int = 8088
    dev_api_key: str = "meg_local_devkey00000000000000000001"
    dev_api_key_b: str = "meg_local_tenantb00000000000000000002"
    default_tenant_slug: str = "demo"
    auth_disabled: bool = False  # AUTH_DISABLED=true for local smoke tests only
    rate_limit_per_minute: int = 120
    osm_extract_path: str = "data/osm/zimbabwe-harare-bulawayo.osm"
    worker_interval_seconds: int = 60
    webhook_max_attempts: int = 8
    graph_refresh_dir: str = "data/osm/.graph_refresh"

    @property
    def effective_use_app_role(self) -> bool:
        return bool(self.use_app_role and self.database_app_url and self.use_persistence)


@lru_cache
def get_settings() -> Settings:
    return Settings()
