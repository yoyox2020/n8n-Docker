from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Mistika AI
    # Default ke Mistika resmi — override di .env jika pakai OpenRouter sementara
    mistika_base_url: str = "https://misstika.mst.co.id/llm-router"
    mistika_api_key: str
    mistika_model: str = "deepseek/deepseek-v4-flash"
    mistika_chat_path: str = "/chat/streamchat"
    # Header auth: "x-api-key" untuk Mistika, "Authorization" untuk OpenRouter
    mistika_auth_header: str = "x-api-key"

    # PostgreSQL — shared with n8n instance
    database_url: str  # postgresql+asyncpg://user:pass@postgres:5432/n8n

    # n8n
    n8n_base_url: str = "http://n8n:5678"
    n8n_api_key: str = ""

    # Service
    agent_port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
