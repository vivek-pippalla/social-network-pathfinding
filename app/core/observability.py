import hashlib
import hmac

from app.core.config import settings


def email_identifier(email: str) -> str:
    """Return a keyed, non-reversible identifier for log correlation."""
    normalized = email.strip().lower().encode("utf-8")
    key = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(key, normalized, hashlib.sha256).hexdigest()
