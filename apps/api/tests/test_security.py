from fastapi import HTTPException
import pytest
from app.core.security import hash_password, verify_password, issue_token, read_token

def test_password_hash_and_verify() -> None:
    encoded = hash_password("a-long-test-password")
    assert encoded.startswith("scrypt$")
    assert verify_password("a-long-test-password", encoded)
    assert not verify_password("wrong-password", encoded)

def test_signed_token_round_trip() -> None:
    token = issue_token("user-123")
    assert read_token(token) == "user-123"

def test_tampered_token_is_rejected() -> None:
    token = issue_token("user-123") + "x"
    with pytest.raises(HTTPException) as exc:
        read_token(token)
    assert exc.value.status_code == 401
