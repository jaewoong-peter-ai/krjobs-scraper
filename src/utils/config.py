"""Configuration management using pydantic-settings"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """애플리케이션 설정

    환경변수 또는 .env 파일에서 설정을 로드합니다.
    Cloud Functions 환경에서는 환경변수로 설정을 주입받습니다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 정의되지 않은 환경변수 무시
    )

    # 스토리지 설정
    storage_type: Literal["local", "supabase", "gcs"] = "local"
    data_dir: str = "./data"

    # Supabase 설정
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_key: str | None = None  # alias for supabase_anon_key

    # 스크래핑 설정
    scrape_delay_seconds: float = 1.5
    max_retries: int = 3
    request_timeout: int = 30

    # 로깅
    log_level: str = "INFO"

    # Google Sheets (추후 사용)
    google_sheets_credentials_path: str | None = None
    google_sheets_id: str | None = None

    # Google Cloud Storage (추후 사용)
    gcs_bucket_name: str | None = None
    gcs_credentials_path: str | None = None

    def get_supabase_key(self) -> str | None:
        """Supabase API key (anon_key 우선)"""
        return self.supabase_anon_key or self.supabase_key

    @property
    def data_path(self) -> Path:
        """데이터 저장 경로

        Cloud Functions 환경에서는 /tmp만 쓰기 가능하므로,
        환경변수로 /tmp를 지정할 수 있습니다.
        """
        path = Path(self.data_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def is_cloud_environment(self) -> bool:
        """Cloud Functions 환경인지 확인"""
        return os.getenv("K_SERVICE") is not None or os.getenv("FUNCTION_TARGET") is not None


@lru_cache()
def get_settings() -> Settings:
    """싱글톤 Settings 인스턴스 반환"""
    return Settings()
