from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/app"
    secret_key: str = '1234567890'
    algorithm: str = 'sha256'


    model_config = SettingsConfigDict(
        env_file='../env',
        env_file_encoding='utf-8'
    )