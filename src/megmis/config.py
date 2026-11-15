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

    # Gen 4 failover chains (comma-separated)
    weather_failover: str = "openweather,mock"
    routing_failover: str = "osrm,graphhopper,mock"
    geocode_failover: str = "mock"
    speech_failover: str = "mock"
    # Free Open-Meteo is NON-COMMERCIAL — must be true before prod open-meteo
    open_meteo_commercial_ok: bool = False

    open_meteo_base_url: str = "https://api.open-meteo.com"
    openweather_key: str = ""
    valhalla_url: str = ""
    graphhopper_url: str = ""
    osrm_url: str = "https://router.project-osrm.org"

    # Gen 4 object storage + secrets + retention
    object_store_backend: str = "local"  # local | s3
    object_store_dir: str = "data/object-store"
    audio_retention_days: int = 30
    evidence_retention_days: int = 90
    s3_endpoint: str = ""
    s3_bucket: str = "megmis"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    secret_manager: str = "env"  # env | file | vault-stub
    secret_file: str = ""
    pii_salt: str = "megmis-pii"
    structured_logs: bool = True

    # RLS-enforced app role (Gen 2). When database_app_url is set, prefer it unless USE_APP_ROLE=false.
    database_app_url: str = (
        "postgresql+psycopg://megmis_app:megmis_app@localhost:5433/megmis"
    )
    use_app_role: bool = True

    mcp_transport: str = "http"
    # Comma-separated Host allowlist for Streamable HTTP DNS-rebinding protection.
    # Use host:* for any port. Include public hostname(s) when deploying behind TLS.
    mcp_allowed_hosts: str = (
        "127.0.0.1:*,localhost:*,[::1]:*,testserver,testserver:*"
    )
    mcp_allowed_origins: str = (
        "http://127.0.0.1:*,http://localhost:*,http://[::1]:*,http://testserver:*"
    )
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
