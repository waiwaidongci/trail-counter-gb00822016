from hashlib import pbkdf2_hmac
from hmac import compare_digest
from secrets import token_hex


ITERATIONS = 300_000


def derive(password: str, salt: str) -> str:
    return pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()


def make_hash(password: str) -> str:
    salt = token_hex(16)
    return f'{salt}${derive(password, salt)}'


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split('$', 1)
    return compare_digest(derive(password, salt), digest)
