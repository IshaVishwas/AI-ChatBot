from unittest.mock import patch, MagicMock
from fastapi import status

def create_mock_completion(reply="Cached answer", prompt_tokens=10, completion_tokens=20):
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=reply))]
    mock.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return mock

def test_cache_hit_identical_reply(client):
    """
    Test identical requests return identical reply and report resolution_source=LLM_CACHE.
    Key_id must be null and fallback_attempts must be 0 for cache hits.
    Original token counts must be retained.
    """
    mock_resp = create_mock_completion(reply="Cached constant reply", prompt_tokens=8, completion_tokens=16)

    with patch("litellm.completion", return_value=mock_resp) as mock_call:
        # Request 1: Live Inference
        res1 = client.post("/chat", json={"session_id": "s1", "message": "What is Python?"})
        assert res1.status_code == status.HTTP_200_OK
        data1 = res1.json()
        assert data1["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert data1["metadata"]["key_id"] == "key_1"
        assert data1["reply"] == "Cached constant reply"
        assert mock_call.call_count == 1

        # Request 2: Identical message in separate session -> Cache Hit!
        res2 = client.post("/chat", json={"session_id": "s2", "message": "What is Python?"})
        assert res2.status_code == status.HTTP_200_OK
        data2 = res2.json()
        assert data2["reply"] == "Cached constant reply"
        assert data2["metadata"]["resolution_source"] == "LLM_CACHE"
        assert data2["metadata"]["key_id"] is None
        assert data2["metadata"]["fallback_attempts"] == 0
        assert data2["metadata"]["input_tokens"] == 8
        assert data2["metadata"]["output_tokens"] == 16
        # Model should NOT have been called a second time
        assert mock_call.call_count == 1

def test_cache_isolation_different_messages(client):
    """
    Different messages must NOT incorrectly share cached responses.
    """
    mock_1 = create_mock_completion(reply="Answer 1")
    mock_2 = create_mock_completion(reply="Answer 2")

    with patch("litellm.completion", side_effect=[mock_1, mock_2]) as mock_call:
        res1 = client.post("/chat", json={"session_id": "c1", "message": "Question 1"})
        res2 = client.post("/chat", json={"session_id": "c2", "message": "Question 2"})

        assert res1.json()["reply"] == "Answer 1"
        assert res2.json()["reply"] == "Answer 2"
        assert res1.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert res2.json()["metadata"]["resolution_source"] == "LIVE_INFERENCE"
        assert mock_call.call_count == 2

