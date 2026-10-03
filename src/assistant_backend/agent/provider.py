import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import SecretStr


@dataclass
class ToolCallDelta:
    index: int
    call_id: str = ""
    name: str = ""
    arguments: str = ""


@dataclass
class ChatDelta:
    content: str = ""
    tool_calls: list[ToolCallDelta] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class ProviderFailure(Exception):
    def __init__(self, code: str, retryable: bool) -> None:
        self.code = code
        self.retryable = retryable


class MimoClient:
    """Small OpenAI-compatible client; errors never include provider bodies."""

    def __init__(self, api_key: SecretStr | None, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def stream_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        max_output_tokens: int,
    ) -> Iterator[ChatDelta]:
        if self.api_key is None or not self.api_key.get_secret_value():
            raise ProviderFailure("MODEL_NOT_CONFIGURED", False)
        body = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",
                "stream": False,
                "max_completion_tokens": max_output_tokens,
                "thinking": {"type": "disabled"},
            },
            ensure_ascii=False,
        ).encode()
        request = Request(
            f"{self.base_url}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=35) as response:
                try:
                    result = json.load(response)
                    message = result["choices"][0]["message"]
                    usage = result.get("usage") or {}
                    calls = [
                        ToolCallDelta(
                            index=index,
                            call_id=part["id"],
                            name=part["function"]["name"],
                            arguments=part["function"]["arguments"],
                        )
                        for index, part in enumerate(message.get("tool_calls") or [])
                    ]
                    yield ChatDelta(
                        content=message.get("content") or "",
                        tool_calls=calls,
                        input_tokens=int(usage.get("prompt_tokens", 0)),
                        output_tokens=int(usage.get("completion_tokens", 0)),
                    )
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise ProviderFailure("MODEL_INVALID_RESPONSE", True) from exc
        except HTTPError as exc:
            status = exc.code
            if status == 401:
                raise ProviderFailure("MODEL_AUTH_FAILED", False) from None
            if status == 403:
                raise ProviderFailure("MODEL_ACCESS_DENIED", False) from None
            if status == 429:
                raise ProviderFailure("MODEL_RATE_LIMITED", True) from None
            raise ProviderFailure("MODEL_PROVIDER_ERROR", status >= 500) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderFailure("MODEL_UNAVAILABLE", True) from exc
