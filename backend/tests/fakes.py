from app.llm.base import LLMError, LLMResponse, Message, ToolCall, Usage


class FakeLLM:
    """Replays scripted responses and records what it was sent.

    Lets us test the agent loop deterministically, with no model or network.
    """
    model = "fake-model"

    def __init__(self, *responses: LLMResponse | Exception) -> None:
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    async def complete(self, messages, tools):
        self.calls.append(list(messages))
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def text(content: str) -> LLMResponse:
    return LLMResponse(text=content, tool_calls=[], usage=Usage(input_tokens=10, output_tokens=5))


def calls(*specs: tuple[str, str]) -> LLMResponse:
    return LLMResponse(
        text=None,
        tool_calls=[ToolCall(id=f"call_{i}", name=n, arguments=a) for i, (n, a) in enumerate(specs)],
        usage=Usage(input_tokens=10, output_tokens=5),
    )


__all__ = ["FakeLLM", "LLMError", "text", "calls"]
