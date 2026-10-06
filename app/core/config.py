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
    RESET_TOKEN_EXPIRE_MINUTES: int = env.int('RESET_TOKEN_EXPIRE_MINUTES', 15)
    RESET_CODE_MAX_ATTEMPTS: int = env.int('RESET_CODE_MAX_ATTEMPTS', 5)

    SMTP_HOST: str = env.str('SMTP_HOST')
    SMTP_PORT: int = env.int('SMTP_PORT', 587)
    SMTP_USER: str = env.str('SMTP_USER')
    SMTP_PASSWORD: str = env.str('SMTP_PASSWORD')
    EMAIL_FROM: str = env.str('EMAIL_FROM')

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()