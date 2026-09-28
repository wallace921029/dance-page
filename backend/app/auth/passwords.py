from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()

# 用户名不存在时也做一次同样耗时的校验，避免通过响应时间判断用户名是否存在
_DUMMY_HASH = _hasher.hash("dance-page-dummy-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """password_hash 为 None（用户不存在）时照常校验一次假哈希，然后返回 False。"""
    try:
        _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
