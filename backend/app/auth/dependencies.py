from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import Account
from app.auth.roles import Role
from app.auth.tokens import identify
from app.database import Session
from app.errors import Problem


bearer = HTTPBearer(auto_error=False)


def account(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    error = Problem(401, 'unauthenticated', 'A valid bearer token is required')
    if not credentials:
        raise error
    try:
        email = identify(credentials.credentials)
    except jwt.InvalidTokenError:
        raise error from None
    with Session() as db:
        user = db.get(Account, email)
    if user is None:
        raise error
    return user


def require(role: Role):
    def authorized(user: Annotated[Account, Depends(account)]):
        if user.role != role:
            raise Problem(403, 'forbidden', f'This operation requires the {role.value} role')
        return user
    return authorized
