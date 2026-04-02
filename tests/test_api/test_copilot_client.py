"""Tests for Copilot SDK adapter client."""

from __future__ import annotations

import sys
import types

import pytest

from openharness.api.client import ApiMessageRequest
from openharness.api.copilot_client import CopilotSdkApiClient
from openharness.api.errors import RequestFailure
from openharness.engine.messages import ConversationMessage


class _EventData:
    def __init__(self, *, delta_content: str = "", content: str = "") -> None:
        self.delta_content = delta_content
        self.content = content


class _Event:
    def __init__(self, event_type: str, data: _EventData | None = None) -> None:
        self.type = event_type
        self.data = data


class _FakeSession:
    def __init__(self) -> None:
        self._handlers = []
        self.disconnected = False

    def on(self, handler):
        self._handlers.append(handler)

        def _unsubscribe():
            if handler in self._handlers:
                self._handlers.remove(handler)

        return _unsubscribe

    async def send(self, prompt: str) -> None:
        assert prompt == "hello"
        for handler in list(self._handlers):
            handler(_Event("assistant.message_delta", _EventData(delta_content="Hel")))
            handler(_Event("assistant.message_delta", _EventData(delta_content="lo")))
            handler(_Event("assistant.message", _EventData(content="Hello")))
            handler(_Event("session.idle"))

    async def disconnect(self) -> None:
        self.disconnected = True


class _FakeClient:
    def __init__(self, config=None) -> None:
        self.config = config
        self.started = False
        self.stopped = False
        self.created_with = None

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def create_session(self, **kwargs):
        self.created_with = kwargs
        return _FakeSession()

    async def list_models(self):
        return [{"id": "gpt-5"}, {"id": "gpt-4.1"}]


def _install_fake_copilot_modules(monkeypatch):
    fake_copilot = types.ModuleType("copilot")
    fake_copilot.CopilotClient = _FakeClient

    fake_copilot_types = types.ModuleType("copilot.types")

    class _PermissionRequestResult:
        def __init__(self, kind: str = "approved", **kwargs) -> None:
            self.kind = kind
            self.kwargs = kwargs

    fake_copilot_types.PermissionRequestResult = _PermissionRequestResult

    monkeypatch.setitem(sys.modules, "copilot", fake_copilot)
    monkeypatch.setitem(sys.modules, "copilot.types", fake_copilot_types)


@pytest.mark.asyncio
async def test_stream_message_emits_deltas_and_complete(monkeypatch):
    _install_fake_copilot_modules(monkeypatch)
    client = CopilotSdkApiClient()

    request = ApiMessageRequest(
        model="gpt-5",
        messages=[ConversationMessage.from_user_text("hello")],
    )

    events = []
    async for event in client.stream_message(request):
        events.append(event)

    assert len(events) == 3
    assert events[0].text == "Hel"
    assert events[1].text == "lo"
    assert events[2].message.text == "Hello"


@pytest.mark.asyncio
async def test_resolve_model_falls_back_to_first_available(monkeypatch):
    _install_fake_copilot_modules(monkeypatch)
    client = CopilotSdkApiClient()

    selected, warning = await client.resolve_model("not-available")

    assert selected == "gpt-5"
    assert "not available" in (warning or "")


@pytest.mark.asyncio
async def test_missing_sdk_raises_request_failure(monkeypatch):
    monkeypatch.setitem(sys.modules, "copilot", types.ModuleType("copilot"))
    monkeypatch.delitem(sys.modules, "copilot.types", raising=False)

    client = CopilotSdkApiClient()
    with pytest.raises(RequestFailure, match="Copilot SDK"):
        await client.list_models()
