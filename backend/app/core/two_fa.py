"""2FA TOTP."""

import pyotp
from typing import Tuple


def generate_secret() -> str:
    return pyotp.random_base32()


def get_provisioning_uri(email: str, secret: str, issuer: str = "Dorvey") -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
