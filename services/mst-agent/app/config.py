from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # === Primary LLM: Mistika-AI ===
    mistika_base_url: str = "https://misstika.mst.co.id/llm-router"
    mistika_api_key: str = ""
    mistika_model: str = ""
    mistika_chat_path: str = "/chat/streamchat"
    mistika_auth_header: str = "x-api-key"

    # === Fallback LLM: Ollama (lokal) ===
    ollama_base_url: str = "http://host.docker.internal:11434/v1"
    ollama_api_key: str = "ollama"
    ollama_model: str = "llama3.2:3b"
    ollama_chat_path: str = "/chat/completions"
    ollama_auth_header: str = "Authorization"
    # Set false untuk production (wajib Mistika-AI, Ollama tidak dipakai)
    ollama_enabled: bool = True

    # PostgreSQL — shared with n8n instance
    database_url: str  # postgresql+asyncpg://user:pass@postgres:5432/n8n

    # n8n
    n8n_base_url: str = "http://n8n:5678"
    n8n_api_key: str = ""
    # Dipakai nodes_registry untuk login dan fetch daftar node lengkap
    n8n_admin_email: str = ""
    n8n_admin_password: str = ""

    # Service
    agent_port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
