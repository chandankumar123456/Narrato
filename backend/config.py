from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
load_dotenv()
class Settings(BaseSettings):
    llm_provider: str = "openai"
    openai_api_key: str = ""
    anthropic_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"

    unsplash_access_key: str | None = None
    pexels_api_key: str | None = None
    image_provider: str = "unsplash"

    output_dir: str = "./outputs"
    file_retention_seconds: int = 3600
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

