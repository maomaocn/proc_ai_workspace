from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import decode_access_token, hash_password, verify_password


def test_password_is_hashed_and_verifiable() -> None:
    password_hash = hash_password("StrongPassword123!")

    assert password_hash != "StrongPassword123!"
    assert verify_password("StrongPassword123!", password_hash)
    assert not verify_password("incorrect-password", password_hash)


def test_expired_access_token_is_rejected() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "roles": ["EMPLOYEE"],
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AppError) as error:
        decode_access_token(token)

    assert error.value.status_code == 401
    assert error.value.code == "UNAUTHORIZED"
