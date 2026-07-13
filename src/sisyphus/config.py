"""Configuração via pydantic-settings (ADR-008). Nada de segredo/flag no código."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SISYPHUS_", env_file=".env", extra="ignore")

    # Fontes
    wikiquote_api: str = "https://pt.wikiquote.org/w/api.php"
    wikidata_api: str = "https://www.wikidata.org/w/api.php"

    # Boa cidadania com as APIs Wikimedia: identifique o cliente (com contato).
    user_agent: str = "sisyphus/0.1 (https://github.com/leonardo-michelotti/sisyphus-api)"

    # Rede e cache (ADR-005: TTL, começa em memória)
    http_timeout: float = 10.0
    cache_ttl: int = 86_400  # 24h — frases/bio mudam pouco
    cache_maxsize: int = 512

    # Rate limit (ADR-014) e cache HTTP (ADR-021)
    rate_limit: int = 60  # requisições por janela, por IP
    rate_window: int = 60  # janela em segundos
    http_cache_max_age: int = 3600  # Cache-Control max-age (s) das respostas /v1

    # App
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"
    log_format: str = "json"  # json (prod) | text (dev legível)
    debug: bool = False


settings = Settings()
