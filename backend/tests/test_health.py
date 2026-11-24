from fastapi import status
from app.config import settings

def test_health_success(client):
    """
    Test GET /health returns status ok, configured keys count >= 2, and cache_enabled.
    """
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert data["keys_configured"] >= 2
    assert isinstance(data["cache_enabled"], bool)

def test_cors_preflight_chat(client):
    """
    Test OPTIONS /chat preflight request from Vite frontend (localhost:5173).
    Must allow origin, POST method, and Content-Type / X-Simulate-Failure headers.
    """
    response = client.options(
        "/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Simulate-Failure"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    allowed_headers = response.headers.get("access-control-allow-headers", "").lower()
    assert "content-type" in allowed_headers
    assert "x-simulate-failure" in allowed_headers

