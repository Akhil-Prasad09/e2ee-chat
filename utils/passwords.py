"""
Server-side password hashing for login: salted scrypt, stored as "scrypt$<salt hex>$<hash hex>".
(Separate from E2EE: the password authenticates you to the relay and unlocks your local key file.)
"""
import hashlib
import hmac
import os

SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    return f'scrypt${salt.hex()}${hashlib.scrypt(password.encode("utf-8"), salt=salt, **SCRYPT).hex()}'


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = stored.split('$')
    except (ValueError, AttributeError):
        return False
    if scheme != 'scrypt':
        return False
    digest = hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt_hex), **SCRYPT)
    return hmac.compare_digest(digest.hex(), digest_hex)
