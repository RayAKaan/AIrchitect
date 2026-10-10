from fastapi.testclient import TestClient

from app.main import app


def test_api_responses_include_security_headers() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert response.headers["Permissions-Policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Request-Id"]


def test_safe_caller_request_id_is_preserved() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-Id": "request.123-abc"})

    assert response.headers["X-Request-Id"] == "request.123-abc"


def test_unsafe_caller_request_id_is_replaced() -> None:
    response = TestClient(app).get("/health", headers={"X-Request-Id": "bad/request"})

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] != "bad/request"
    assert len(response.headers["X-Request-Id"]) == 36
