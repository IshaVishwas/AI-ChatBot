from unittest.mock import patch, MagicMock
from fastapi import status

def create_mock_completion(reply="Hello from model", prompt_tokens=10, completion_tokens=20):
    mock = MagicMock()
    mock.choices = [MagicMock(message=MagicMock(content=reply))]
    mock.usage = MagicMock(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return mock

def test_chat_success_metadata_and_persistence(client):
    """
    Test successful POST /chat returns required fields and metadata contract.
    """
    mock_resp = create_mock_completion(reply="I am your assistant", prompt_tokens=15, completion_tokens=25)
    with patch("litellm.completion", return_value=mock_resp):
        payload = {
            "session_id": "session_1",
            "message": "Hello AI",
            "system_prompt": "You are a helpful assistant"
        }
        response = client.post("/chat", json=payload)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["session_id"] == "session_1"
        assert data["reply"] == "I am your assistant"

        meta = data["metadata"]
        assert meta["resolution_source"] == "LIVE_INFERENCE"
        assert meta["key_id"] == "key_1"
        assert meta["fallback_attempts"] == 0
        assert meta["input_tokens"] == 15
        assert meta["output_tokens"] == 25
        assert isinstance(meta["latency_ms"], int)
        assert meta["latency_ms"] >= 0

def test_multi_turn_memory(client):
    """
    Test multi-turn conversation maintains history across turns and passes history to model.
    """
    mock_1 = create_mock_completion(reply="First reply")
    mock_2 = create_mock_completion(reply="Second reply")

    with patch("litellm.completion", side_effect=[mock_1, mock_2]) as mock_call:
        # Turn 1
        client.post("/chat", json={"session_id": "multi_turn", "message": "Turn 1"})
        assert mock_call.call_count == 1
        turn1_messages = mock_call.call_args_list[0][1]["messages"]
        assert len(turn1_messages) == 1
        assert turn1_messages[0]["content"] == "Turn 1"

        # Turn 2
        client.post("/chat", json={"session_id": "multi_turn", "message": "Turn 2"})
        assert mock_call.call_count == 2
        turn2_messages = mock_call.call_args_list[1][1]["messages"]
        # History should include Turn 1 user message, First reply assistant message, and Turn 2 user message
        assert len(turn2_messages) == 3
        assert turn2_messages[0] == {"role": "user", "content": "Turn 1"}
        assert turn2_messages[1] == {"role": "assistant", "content": "First reply"}
        assert turn2_messages[2] == {"role": "user", "content": "Turn 2"}

def test_session_isolation(client):
    """
    Test two separate sessions do not share history.
    """
    mock_1 = create_mock_completion(reply="Reply A")
    mock_2 = create_mock_completion(reply="Reply B")

    with patch("litellm.completion", side_effect=[mock_1, mock_2]) as mock_call:
        client.post("/chat", json={"session_id": "session_A", "message": "Message A"})
        client.post("/chat", json={"session_id": "session_B", "message": "Message B"})

        # Session B call should only have Message B, NOT Message A
        b_messages = mock_call.call_args_list[1][1]["messages"]
        assert len(b_messages) == 1
        assert b_messages[0]["content"] == "Message B"

def test_get_session_messages_history(client):
    """
    Test GET /sessions/{session_id}/messages returns stored messages oldest first.
    """
    mock_1 = create_mock_completion(reply="Reply 1")
    with patch("litellm.completion", return_value=mock_1):
        client.post("/chat", json={"session_id": "hist_session", "message": "Hello 1"})

    res = client.get("/sessions/hist_session/messages")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["session_id"] == "hist_session"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][0]["content"] == "Hello 1"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content"] == "Reply 1"
    assert "metadata" in data["messages"][1]

def test_get_unknown_session_returns_404(client):
    """
    Unknown session must return HTTP 404 {"detail": "session not found"}.
    """
    res = client.get("/sessions/non_existent_session/messages")
    assert res.status_code == status.HTTP_404_NOT_FOUND
    assert res.json()["detail"] == "session not found"

def test_list_and_delete_sessions(client):
    """
    Test GET /sessions lists all conversation sessions with titles, and DELETE /sessions/{session_id} deletes it.
    """
    mock_1 = create_mock_completion(reply="Answer 1")
    mock_2 = create_mock_completion(reply="Answer 2")
    with patch("litellm.completion", side_effect=[mock_1, mock_2]):
        client.post("/chat", json={"session_id": "sess_alpha", "message": "What is machine learning?"})
        client.post("/chat", json={"session_id": "sess_beta", "message": "Tell me a joke"})

    # Test GET /sessions
    res = client.get("/sessions")
    assert res.status_code == status.HTTP_200_OK
    sessions = res.json()
    assert len(sessions) == 2
    # Verify titles generated from first user message
    ids = [s["session_id"] for s in sessions]
    assert "sess_alpha" in ids
    assert "sess_beta" in ids
    for s in sessions:
        assert s["updated_at"] is not None
        assert s["updated_at"].endswith("Z")
        if s["session_id"] == "sess_alpha":
            assert "machine learning" in s["title"]
            assert s["message_count"] == 2

    # Test DELETE /sessions/sess_alpha
    del_res = client.delete("/sessions/sess_alpha")
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["status"] == "deleted"

    # Verify session is no longer in list
    res_after = client.get("/sessions")
    assert len(res_after.json()) == 1
    assert res_after.json()[0]["session_id"] == "sess_beta"

def test_session_timestamp_utc_formatting(client):
    """
    Verify session timestamps are returned in ISO 8601 UTC format ending in 'Z',
    and accurately match current UTC time.
    """
    from datetime import datetime, timezone
    mock_resp = create_mock_completion(reply="Timestamp verification")
    before_call = datetime.now(timezone.utc)

    with patch("litellm.completion", return_value=mock_resp):
        client.post("/chat", json={"session_id": "time_test", "message": "Verify timestamp format"})

    res = client.get("/sessions")
    assert res.status_code == status.HTTP_200_OK
    session = next((s for s in res.json() if s["session_id"] == "time_test"), None)
    assert session is not None
    ts_str = session["updated_at"]
    assert ts_str is not None
    assert ts_str.endswith("Z")

    # Parse and verify parsed UTC timestamp is within 5 seconds of test run
    parsed_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    assert parsed_dt.tzinfo == timezone.utc
    diff_seconds = abs((datetime.now(timezone.utc) - parsed_dt).total_seconds())
    assert diff_seconds < 5.0

def test_multiple_conversations_persistence_and_isolation(client):
    """
    Test creating multiple conversations, verifying all appear in /sessions,
    verifying messages remain isolated per session, and selective deletion.
    """
    mock_resp = create_mock_completion(reply="Standard reply")

    with patch("litellm.completion", return_value=mock_resp):
        # Conversation 1: 2 turns (4 messages)
        client.post("/chat", json={"session_id": "conv_1", "message": "First message in conv 1"})
        client.post("/chat", json={"session_id": "conv_1", "message": "Second message in conv 1"})

        # Conversation 2: 1 turn (2 messages)
        client.post("/chat", json={"session_id": "conv_2", "message": "First message in conv 2"})

    # Verify both conversations in /sessions
    res = client.get("/sessions")
    assert res.status_code == status.HTTP_200_OK
    session_map = {s["session_id"]: s for s in res.json()}
    assert "conv_1" in session_map
    assert "conv_2" in session_map
    assert session_map["conv_1"]["message_count"] == 4
    assert session_map["conv_2"]["message_count"] == 2

    # Verify message retrieval isolation
    conv1_res = client.get("/sessions/conv_1/messages")
    assert conv1_res.status_code == status.HTTP_200_OK
    assert len(conv1_res.json()["messages"]) == 4

    conv2_res = client.get("/sessions/conv_2/messages")
    assert conv2_res.status_code == status.HTTP_200_OK
    assert len(conv2_res.json()["messages"]) == 2

    # Selectively delete conversation 1
    del_res = client.delete("/sessions/conv_1")
    assert del_res.status_code == status.HTTP_200_OK

    # Verify conv_1 is deleted but conv_2 remains intact
    after_res = client.get("/sessions")
    remaining_ids = [s["session_id"] for s in after_res.json()]
    assert "conv_1" not in remaining_ids
    assert "conv_2" in remaining_ids



