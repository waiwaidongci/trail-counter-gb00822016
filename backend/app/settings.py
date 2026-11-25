import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    jwt_secret: str
    seed_demo: bool
    max_upload_bytes: int = 2 * 1024 * 1024
    max_rows: int = 5000

    @classmethod
    def from_env(cls):
        secret = os.environ['JWT_SECRET']
        if len(secret) < 32:
            raise ValueError('JWT_SECRET must be at least 32 characters')
        return cls(os.environ['DATABASE_URL'], os.environ['REDIS_URL'], secret,
                   os.environ.get('SEED_DEMO', 'true').lower() == 'true')


settings = Settings.from_env()
