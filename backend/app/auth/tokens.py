from datetime import datetime, timedelta, timezone

import jwt

from app.settings import settings


AUDIENCE = 'analytics-api'


def issue(email: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {'sub': email, 'iat': now, 'exp': now + timedelta(hours=4), 'aud': AUDIENCE}
    return jwt.encode(claims, settings.jwt_secret, algorithm='HS256')


def identify(token: str) -> str:
    claims = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'], audience=AUDIENCE,
                        options={'require': ['sub', 'iat', 'exp']})
    return claims['sub']
