import io
import json
from urllib.error import HTTPError

import pytest
from pydantic import SecretStr

from assistant_backend.agent.provider import MimoClient, ProviderFailure


class FakeResponse(io.BytesIO):
    def __init__(self, value: dict) -> None:
        super().__init__(json.dumps(value).encode())

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def test_mimo_client_parses_tool_response_and_keeps_api_key_in_header(monkeypatch) -> None:
    seen = {}
    response = FakeResponse(
        {
            "choices": [
                {
                    "message": {
                        "content": "Hello",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {"name": "get_task", "arguments": '{"task_id":"abc"}'},
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4},
        }
    )

    def fake_urlopen(request, timeout):
        seen["request"] = request
        seen["timeout"] = timeout
        return response

    monkeypatch.setattr("assistant_backend.agent.provider.urlopen", fake_urlopen)
    client = MimoClient(
        SecretStr("unit-test-key"), "https://api.xiaomimimo.com/v1", "mimo-v2.6-flash"
    )
    chunks = list(client.stream_chat([{"role": "user", "content": "test"}], [], 8))
    assert "Hello" == "".join(chunk.content for chunk in chunks)
    assert chunks[0].tool_calls[0].name == "get_task"
    assert chunks[0].tool_calls[0].arguments == '{"task_id":"abc"}'
    assert chunks[-1].input_tokens == 12
    assert chunks[-1].output_tokens == 4
    assert seen["request"].full_url == "https://api.xiaomimimo.com/v1/chat/completions"
    assert seen["request"].get_header("Authorization") == "Bearer unit-test-key"
    assert seen["timeout"] == 35
    request_body = json.loads(seen["request"].data)
    assert request_body["model"] == "mimo-v2.6-flash"
    assert request_body["max_completion_tokens"] == 8
    assert request_body["stream"] is False
    assert request_body["thinking"] == {"type": "disabled"}


@pytest.mark.parametrize(
    ("http_status", "expected_code"),
    [(401, "MODEL_AUTH_FAILED"), (403, "MODEL_ACCESS_DENIED")],
)
def test_mimo_client_maps_provider_auth_failure_without_response_body(
    monkeypatch, http_status: int, expected_code: str
) -> None:
    def unauthorized(_request, timeout):
        del timeout
        raise HTTPError(
            "https://api.xiaomimimo.com/v1/chat/completions",
            http_status,
            "Unauthorized",
            {},
            io.BytesIO(b"sensitive provider response"),
        )

    monkeypatch.setattr("assistant_backend.agent.provider.urlopen", unauthorized)
    client = MimoClient(
        SecretStr("unit-test-key"), "https://api.xiaomimimo.com/v1", "mimo-v2.6-flash"
    )
    with pytest.raises(ProviderFailure) as error:
        list(client.stream_chat([{"role": "user", "content": "test"}], [], 8))
    assert error.value.code == expected_code
    assert "sensitive" not in str(error.value)


def test_mimo_base_url_cannot_send_key_to_unapproved_host() -> None:
    from assistant_backend.config import Settings

    with pytest.raises(ValueError, match="official HTTPS API endpoint"):
        Settings(_env_file=None, mimo_base_url="https://not-mimo.example/v1")
