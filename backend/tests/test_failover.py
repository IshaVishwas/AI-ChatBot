from unittest.mock import patch, MagicMock
import logging
from fastapi import status
from app.config import settings

def create_mock_completion(reply="Success from provider", prompt_tokens=12, completion_tokens=18):
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=reply))]
    mock.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return mock

def test_gemini_primary_success(client):
    """
    Provider 1 (Gemini) succeeds on first attempt.
    Verify metadata reports gemini provider, gemini-2.5-flash model, key_1, and fallback_attempts=0.
    """
    mock_success = create_mock_completion(reply="Hello from Gemini")

    with patch("litellm.completion", return_value=mock_success) as mock_call:
        res = client.post("/chat", json={"session_id": "gemini_success_sess", "message": "Hi Gemini"})
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["reply"] == "Hello from Gemini"

        meta = data["metadata"]
        assert meta["resolution_source"] == "LIVE_INFERENCE"
        assert meta["source"] == "LIVE_INFERENCE"
        assert meta["provider"] == "gemini"
        assert "gemini" in meta["model"]
        assert meta["key_id"] == "key_1"
        assert meta["fallback_attempts"] == 0
        assert meta["session_id"] == "gemini_success_sess"

        # Verify litellm call parameters
        assert mock_call.call_count == 1
        called_kwargs = mock_call.call_args[1]
        assert "gemini" in called_kwargs["model"]
        assert called_kwargs["api_key"] == settings.gemini_api_key_val

def test_gemini_quota_exhaustion_429_failover_to_nvidia(client):
    """
    Gemini fails with 429 quota exhaustion. Backend automatically fails over
    to Provider 2 (NVIDIA Nemotron through OpenRouter).
    """
    mock_nvidia = create_mock_completion(reply="Hello from NVIDIA Nemotron")

    with patch(
        "litellm.completion",
        side_effect=[Exception("ResourceExhausted: 429 Quota exceeded for quota metric 'GenerateContent'"), mock_nvidia]
    ) as mock_call:
        res = client.post("/chat", json={"session_id": "quota_sess", "message": "Test quota failover"})
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["reply"] == "Hello from NVIDIA Nemotron"

        meta = data["metadata"]
        assert meta["resolution_source"] == "LIVE_INFERENCE"
        assert meta["provider"] == "openrouter"
        assert meta["model"] == "openrouter/nvidia/nemotron-3.5-lightning:free"
        assert meta["key_id"] == "key_2"
        assert meta["fallback_attempts"] == 1

        assert mock_call.call_count == 2
        # First call was Gemini
        assert "gemini" in mock_call.call_args_list[0][1]["model"]
        assert mock_call.call_args_list[0][1]["api_key"] == settings.gemini_api_key_val

        # Second call was OpenRouter NVIDIA
        assert mock_call.call_args_list[1][1]["model"] == "openrouter/nvidia/nemotron-3.5-lightning:free"
        assert mock_call.call_args_list[1][1]["api_key"] == settings.openrouter_api_key_val

def test_gemini_auth_failure_failover_to_nvidia(client):
    """
    Gemini fails with 401/Authentication error. Backend automatically fails over to NVIDIA Nemotron.
    """
    mock_nvidia = create_mock_completion(reply="NVIDIA response after auth failure")

    with patch(
        "litellm.completion",
        side_effect=[Exception("AuthenticationError: 401 API_KEY_INVALID"), mock_nvidia]
    ) as mock_call:
        res = client.post("/chat", json={"session_id": "auth_sess", "message": "Test auth failover"})
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["reply"] == "NVIDIA response after auth failure"
        assert data["metadata"]["provider"] == "openrouter"
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1
        assert mock_call.call_count == 2

def test_gemini_timeout_failover_to_nvidia(client):
    """
    Gemini times out. Backend automatically fails over to NVIDIA Nemotron.
    """
    mock_nvidia = create_mock_completion(reply="NVIDIA response after timeout")

    with patch(
        "litellm.completion",
        side_effect=[TimeoutError("ReadTimeout: Gemini connection timed out after 30s"), mock_nvidia]
    ) as mock_call:
        res = client.post("/chat", json={"session_id": "timeout_sess", "message": "Test timeout failover"})
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["reply"] == "NVIDIA response after timeout"
        assert data["metadata"]["provider"] == "openrouter"
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1
        assert mock_call.call_count == 2

def test_both_providers_failing_returns_503(client):
    """
    When both Gemini and OpenRouter/NVIDIA fail, return HTTP 503 {"detail": "all providers unavailable"}.
    Failed messages must NOT be persisted in SQLite.
    """
    with patch(
        "litellm.completion",
        side_effect=[
            Exception("Gemini error 500"),
            Exception("OpenRouter error 503")
        ]
    ) as mock_call:
        res = client.post(
            "/chat",
            json={"session_id": "both_fail_sess", "message": "Both fail test"}
        )
        assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert res.json()["detail"] == "all providers unavailable"
        assert mock_call.call_count == 2

        # Verify session was NOT persisted to SQLite
        history_res = client.get("/sessions/both_fail_sess/messages")
        assert history_res.status_code == status.HTTP_404_NOT_FOUND

def test_openrouter_prefix_and_exclusive_api_keys(client):
    """
    Verify:
    1. OpenRouter model has 'openrouter/' prefix.
    2. OPENROUTER_API_KEY is used exclusively for the OpenRouter fallback.
    3. GEMINI_API_KEY is NOT passed to OpenRouter.
    """
    mock_nvidia = create_mock_completion(reply="OpenRouter reply")

    with patch(
        "litellm.completion",
        side_effect=[Exception("Gemini unavailable"), mock_nvidia]
    ) as mock_call:
        res = client.post("/chat", json={"session_id": "keys_isolation_sess", "message": "Verify keys"})
        assert res.status_code == status.HTTP_200_OK

        call_gemini = mock_call.call_args_list[0][1]
        call_openrouter = mock_call.call_args_list[1][1]

        # Verify OpenRouter model prefix
        assert call_openrouter["model"].startswith("openrouter/")
        assert "nvidia/nemotron" in call_openrouter["model"]

        # Verify distinct keys
        assert call_gemini["api_key"] == settings.gemini_api_key_val
        assert call_openrouter["api_key"] == settings.openrouter_api_key_val

def test_simulation_key_1_429(client):
    """
    X-Simulate-Failure: key_1=429 causes Gemini to fail, automatically falling back to NVIDIA on key_2.
    """
    mock_success = create_mock_completion(reply="Success on NVIDIA via OpenRouter")

    with patch("litellm.completion", return_value=mock_success) as mock_call:
        headers = {"X-Simulate-Failure": "key_1=429"}
        res = client.post(
            "/chat",
            json={"session_id": "sim_429", "message": "Simulate 429"},
            headers=headers
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["metadata"]["provider"] == "openrouter"
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1
        assert mock_call.call_count == 1
        assert mock_call.call_args[1]["model"] == "openrouter/nvidia/nemotron-3.5-lightning:free"

def test_simulation_named_gemini_429(client):
    """
    X-Simulate-Failure: gemini=429 causes Gemini to fail, falling back to NVIDIA.
    """
    mock_success = create_mock_completion(reply="Success on NVIDIA after gemini simulation")

    with patch("litellm.completion", return_value=mock_success) as mock_call:
        headers = {"X-Simulate-Failure": "gemini=429"}
        res = client.post(
            "/chat",
            json={"session_id": "sim_gemini", "message": "Simulate gemini failure"},
            headers=headers
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["metadata"]["provider"] == "openrouter"
        assert data["metadata"]["key_id"] == "key_2"
        assert data["metadata"]["fallback_attempts"] == 1

def test_simulation_wildcard_all_fail(client):
    """
    X-Simulate-Failure: *=429 simulates failure across all providers, returning 503.
    """
    headers = {"X-Simulate-Failure": "*=429"}
    res = client.post(
        "/chat",
        json={"session_id": "sim_wildcard", "message": "Wildcard simulation"},
        headers=headers
    )
    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert res.json()["detail"] == "all providers unavailable"

def test_simulation_disabled_behavior(client, monkeypatch):
    """
    When ENABLE_FAILURE_SIMULATION=false, X-Simulate-Failure header is ignored.
    """
    monkeypatch.setattr(settings, "ENABLE_FAILURE_SIMULATION", False)
    mock_success = create_mock_completion(reply="Sim ignored")

    with patch("litellm.completion", return_value=mock_success):
        headers = {"X-Simulate-Failure": "*=429"}
        res = client.post(
            "/chat",
            json={"session_id": "sim_disabled", "message": "Should ignore simulation"},
            headers=headers
        )
        assert res.status_code == status.HTTP_200_OK
        assert res.json()["metadata"]["key_id"] == "key_1"
        assert res.json()["metadata"]["provider"] == "gemini"
        assert res.json()["metadata"]["fallback_attempts"] == 0

def test_no_secret_keys_leak_in_logs_or_errors(client, caplog):
    """
    Ensure provider API keys are never exposed in log outputs or error messages.
    """
    fake_secret = "AIzaSy_SecretKey_123456789"
    with patch.object(settings, "GEMINI_API_KEY", fake_secret):
        with patch(
            "litellm.completion",
            side_effect=Exception(f"Failed to connect with key {fake_secret} and url https://api.google.com?key={fake_secret}")
        ):
            with caplog.at_level(logging.WARNING):
                res = client.post("/chat", json={"session_id": "leak_test", "message": "Test leak"})
                assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

                # Verify secret key is NOT in response JSON
                assert fake_secret not in res.text

                # Verify secret key is redacted in all logged messages
                for record in caplog.records:
                    assert fake_secret not in record.message
                    if "[REDACTED" in record.message:
                        assert "[REDACTED" in record.message
