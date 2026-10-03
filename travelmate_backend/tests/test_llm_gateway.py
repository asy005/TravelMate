from unittest.mock import patch, MagicMock

from app.services import llm_gateway


def _mock_response():
    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
    return mock_resp


def test_groq_is_the_default_provider(monkeypatch):
    monkeypatch.setattr(llm_gateway.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(llm_gateway.settings, "GROQ_API_KEY", "test-key")

    with patch("app.services.llm_gateway.requests.post", return_value=_mock_response()) as mock_post:
        result = llm_gateway.chat_completion([{"role": "user", "content": "hi"}])

    assert result == "hello"
    called_url = mock_post.call_args[0][0]
    assert called_url == llm_gateway.GROQ_URL
    called_headers = mock_post.call_args[1]["headers"]
    assert called_headers["Authorization"] == "Bearer test-key"


def test_provider_swaps_to_openai_via_config_only(monkeypatch):
    """
    Confirms switching providers is purely a Settings/.env change --
    no code path difference beyond which URL/key/model gets used.
    """
    monkeypatch.setattr(llm_gateway.settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(llm_gateway.settings, "OPENAI_API_KEY", "openai-key")
    monkeypatch.setattr(llm_gateway.settings, "OPENAI_MODEL", "gpt-4o-mini")

    with patch("app.services.llm_gateway.requests.post", return_value=_mock_response()) as mock_post:
        result = llm_gateway.chat_completion([{"role": "user", "content": "hi"}])

    assert result == "hello"
    called_url = mock_post.call_args[0][0]
    assert called_url == llm_gateway.OPENAI_URL
    called_headers = mock_post.call_args[1]["headers"]
    assert called_headers["Authorization"] == "Bearer openai-key"


def test_missing_api_key_raises_gateway_error(monkeypatch):
    monkeypatch.setattr(llm_gateway.settings, "LLM_PROVIDER", "groq")
    monkeypatch.setattr(llm_gateway.settings, "GROQ_API_KEY", None)

    try:
        llm_gateway.chat_completion([{"role": "user", "content": "hi"}])
        assert False, "expected LLMGatewayError"
    except llm_gateway.LLMGatewayError:
        pass
