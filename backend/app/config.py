from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，全部来自环境变量（开发时可写在 backend/.env）。"""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    admin_username: str = Field(min_length=1)
    admin_password: str = Field(min_length=6)
    data_dir: Path = Path("data")
    max_upload_mb: int = 200
    # AI 服务商凭据（D82：写在 .env 里，修改后重启生效）
    dashscope_api_key: str = ""
    volcengine_ark_api_key: str = ""
    volcengine_speech_api_key: str = ""
    # 未配置 HTTPS 时必须设为 false，否则浏览器不会保存登录 Cookie
    cookie_secure: bool = True

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'app.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
