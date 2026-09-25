from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "api"}


def test_system_defaults_to_deterministic_provider() -> None:
    response = TestClient(app).get("/api/v1/system")
    assert response.status_code == 200
    assert response.json()["decision_provider"] == "deterministic"
