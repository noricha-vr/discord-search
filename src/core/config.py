"""環境変数・設定管理"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """アプリケーション設定"""

    # Discord
    discord_bot_token: str = ""
    discord_guild_id: str = ""

    # Gemini API
    gemini_api_key: str = ""

    # GCP
    gcp_project_id: str = "discord-search-20260101"
    gcp_region: str = "asia-northeast1"

    # File Search
    file_search_store_name: str = "discord-messages"

    # Sync settings
    sync_interval_seconds: int = 3600  # 1時間
    sync_batch_size: int = 100
    sync_delay_seconds: float = 1.0  # レート制限対策

    # Search settings
    search_result_limit: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
