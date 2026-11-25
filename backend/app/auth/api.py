from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.auth.models import Account
from app.auth.passwords import verify_password
from app.auth.tokens import issue
from app.database import Session
from app.errors import Problem


router = APIRouter(prefix='/auth', tags=['Authentication'])
DUMMY_HASH = ('0' * 32) + '$' + ('0' * 64)


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: str = Field(max_length=120)
    password: str = Field(max_length=120)


@router.post('/login')
def login(payload: Login):
    with Session() as db:
        user = db.get(Account, payload.email.strip().lower())
    valid = verify_password(payload.password, user.password_hash if user else DUMMY_HASH)
    if not valid or user is None:
        raise Problem(401, 'bad_credentials', 'Invalid account or password')
    return {'access_token': issue(user.email), 'token_type': 'bearer', 'role': user.role}
