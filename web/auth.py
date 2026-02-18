"""Code-word authentication and signed cookie management."""

import hmac

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.config import env

_COOKIE_NAME = "ct_session"


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(env.web_secret_key)


def verify_code_word(code: str) -> str | None:
    """Check code against role code-words (constant-time).

    Returns role name ("admin", "model", "teamlead") or None.
    """
    code = code.strip()
    if not code:
        return None

    # Check each role code-word using hmac.compare_digest for timing safety
    if env.web_admin_code and hmac.compare_digest(code, env.web_admin_code):
        return "admin"
    if env.web_teamlead_code and hmac.compare_digest(code, env.web_teamlead_code):
        return "teamlead"
    if env.web_model_code and hmac.compare_digest(code, env.web_model_code):
        return "model"

    return None


def create_session_token(role: str) -> str:
    """Create a signed token encoding the user's role."""
    serializer = _get_serializer()
    return serializer.dumps({"role": role})


def decode_session_token(token: str) -> dict | None:
    """Decode and verify a session token.

    Returns {"role": "..."} or None if invalid/expired.
    """
    serializer = _get_serializer()
    max_age = env.web_cookie_ttl_days * 86400  # days → seconds
    try:
        data = serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

    if not isinstance(data, dict) or "role" not in data:
        return None
    return data


COOKIE_NAME = _COOKIE_NAME
