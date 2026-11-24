from fastapi import status

def test_validation_missing_session_id(client):
    """
    Missing session_id must return 422.
    """
    payload = {"message": "Hello"}
    response = client.post("/chat", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "detail" in response.json()

def test_validation_empty_session_id(client):
    """
    Empty string session_id must return 422.
    """
    payload = {"session_id": "", "message": "Hello"}
    response = client.post("/chat", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_validation_oversized_session_id(client):
    """
    Session_id > 128 chars must return 422.
    """
    payload = {"session_id": "a" * 129, "message": "Hello"}
    response = client.post("/chat", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_validation_missing_message(client):
    """
    Missing message must return 422.
    """
    payload = {"session_id": "test-session"}
    response = client.post("/chat", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_validation_empty_message(client):
    """
    Empty/whitespace-only message must return 422.
    """
    payload = {"session_id": "test-session", "message": "   "}
    response = client.post("/chat", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_validation_oversized_message(client):
    """
    Message over 4000 characters must return 422.
    """
    payload = {"session_id": "test-session", "message": "a" * 4001}
    response = client.post("/chat", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_validation_invalid_json(client):
    """
    Invalid JSON body must return 422.
    """
    response = client.post(
        "/chat",
        content="not-json",
        headers={"Content-Type": "application/json"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

