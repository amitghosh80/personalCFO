from ..config import get_fernet


def encrypt(value: str) -> bytes:
    return get_fernet().encrypt(value.encode("utf-8"))


def decrypt(value: bytes) -> str:
    return get_fernet().decrypt(value).decode("utf-8")
