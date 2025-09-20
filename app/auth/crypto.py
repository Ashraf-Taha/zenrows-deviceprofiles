import secrets
import hashlib
from typing import Tuple

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


PREFIX_HEX_LEN = 12


_ph = PasswordHasher()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def prefix_from_raw(api_key: str) -> str:
    return sha256_hex(api_key.encode("utf-8"))[:PREFIX_HEX_LEN]


def hash_key(raw_key: str) -> bytes:
    return _ph.hash(raw_key).encode("utf-8")


def verify_key(hash_bytes: bytes, raw_key: str) -> bool:
    try:
        _ph.verify(hash_bytes.decode("utf-8"), raw_key)
        return True
    except VerifyMismatchError:
        return False


def generate_api_key() -> Tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, prefix_from_raw(token)
