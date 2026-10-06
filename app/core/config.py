from environs import Env
from pydantic_settings import BaseSettings, SettingsConfigDict


env = Env()
env.read_env()

class Settings(BaseSettings):
    DATABASE_URL: str = env.str('DATABASE_URL')

    SECRET_KEY: str = env.str('SECRET_KEY')
    ALGORITHM: str = env.str('ALGORITHM')

    ACCESS_TOKEN_EXPIRE_MINUTES: int = env.int('ACCESS_TOKEN_EXPIRE_MINUTES')
    REFRESH_TOKEN_EXPIRE_DAYS: int = env.int('REFRESH_TOKEN_EXPIRE_DAYS')

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()