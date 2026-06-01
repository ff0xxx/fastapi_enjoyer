from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/app"
    secret_key: str = '1234567890'
    algorithm: str = 'sha256'


    model_config = SettingsConfigDict(
        env_file='../env',
        env_file_encoding='utf-8'
    )

@lru_cache()
def get_settings():
    return Settings()