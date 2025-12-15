import hmac
import hashlib
from server.core.config import settings


def otp_hash(code: str) -> str:

    secret = settings.OTP_SECRET
    return hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()


def otp_verify(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(otp_hash(code), code_hash)
