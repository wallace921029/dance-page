import secrets

# 去掉容易混淆的 0/O、1/I/L
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 8


def generate_code() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def normalize_code(raw: str) -> str:
    """用户输入的邀请码可能带分隔符、空格或小写，如 "k7m3-q9tx"。"""
    return "".join(ch for ch in raw.upper() if ch.isalnum())
