from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",extra="allow")
    print("model_config", model_config)

    workday_api_base_url: str = "http://127.0.0.1:9001"
    mcp_sse_url: str = "http://127.0.0.1:9002/sse"
    sqlite_path: str = "./loa.db"


settings = Settings()
