"""Copilot SDK-backed API client adapter.

This adapter implements the same streaming contract used by the query engine.
The initial MVP focuses on assistant text responses and keeps tool orchestration
on the OpenHarness side unchanged.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import inspect
from typing import Any

from openharness.api.client import ApiMessageCompleteEvent, ApiMessageRequest, ApiTextDeltaEvent
from openharness.api.errors import AuthenticationFailure, RateLimitFailure, RequestFailure
from openharness.api.usage import UsageSnapshot
from openharness.engine.messages import ConversationMessage, TextBlock


class CopilotSdkApiClient:
    """Thin adapter over the Copilot Python SDK.

    The SDK still requires Copilot CLI to be installed. We keep the dependency
    optional at import-time so Anthropic-only users are unaffected.
    """

    def __init__(
        self,
        *,
        cli_path: str | None = None,
        cli_url: str | None = None,
        github_token: str | None = None,
    ) -> None:
        self._cli_path = cli_path
        self._cli_url = cli_url
        self._github_token = github_token
        self._client: Any | None = None
        self._session: Any | None = None
        self._session_signature: tuple[str, str | None] | None = None
        self._lock = asyncio.Lock()

    async def resolve_model(self, requested_model: str) -> tuple[str, str | None]:
        """Return a supported model name and an optional warning message."""
        models = await self.list_models()
        if not models:
            return requested_model, "could not verify Copilot model availability"
        if requested_model in models:
            return requested_model, None
        return models[0], f"model '{requested_model}' is not available in Copilot; using '{models[0]}'"

    async def list_models(self) -> list[str]:
        """Return available Copilot models when the SDK exposes them."""
        client = await self._ensure_client()
        list_models_fn = getattr(client, "list_models", None)
        if not callable(list_models_fn):
            return []

        models_raw = list_models_fn()
        if inspect.isawaitable(models_raw):
            models_raw = await models_raw

        return _normalize_models(models_raw)

    async def stream_message(self, request: ApiMessageRequest):
        """Send a prompt to Copilot and emit OpenHarness stream events."""
        prompt = _latest_user_prompt(request.messages)
        if not prompt:
            raise RequestFailure("No user prompt found to send to Copilot SDK")

        session = await self._ensure_session(request)
        streamed_parts: list[str] = []
        final_text = ""

        queue: asyncio.Queue[str] = asyncio.Queue()
        done = asyncio.Event()
        final_text_holder: dict[str, str] = {"value": ""}
        unsubscribe: Callable[[], None] | None = None

        on_fn = getattr(session, "on", None)
        if callable(on_fn):
            unsubscribe = on_fn(lambda event: _handle_session_event(event, queue, done, final_text_holder))

        try:
            send_fn = getattr(session, "send", None)
            if callable(send_fn):
                result = send_fn(prompt)
                if inspect.isawaitable(result):
                    await result

                while True:
                    if done.is_set() and queue.empty():
                        break
                    try:
                        delta = await asyncio.wait_for(queue.get(), timeout=0.2)
                    except asyncio.TimeoutError:
                        continue
                    if not delta:
                        continue
                    streamed_parts.append(delta)
                    yield ApiTextDeltaEvent(text=delta)

                final_text = final_text_holder["value"] or "".join(streamed_parts)
            else:
                send_and_wait_fn = getattr(session, "send_and_wait", None)
                if not callable(send_and_wait_fn):
                    raise RequestFailure("Copilot SDK session does not expose send/send_and_wait")
                response = send_and_wait_fn(prompt)
                if inspect.isawaitable(response):
                    response = await response
                final_text = _extract_response_text(response)
                if final_text:
                    yield ApiTextDeltaEvent(text=final_text)
        except Exception as exc:
            raise _translate_copilot_error(exc) from exc
        finally:
            if unsubscribe is not None:
                try:
                    unsubscribe()
                except Exception:
                    pass

        yield ApiMessageCompleteEvent(
            message=ConversationMessage(role="assistant", content=[TextBlock(text=final_text)]),
            usage=UsageSnapshot(),
            stop_reason=None,
        )

    async def aclose(self) -> None:
        """Close Copilot session/client resources if initialized."""
        async with self._lock:
            if self._session is not None:
                try:
                    await self._session.disconnect()
                except Exception:
                    pass
                self._session = None
                self._session_signature = None
            if self._client is not None:
                try:
                    await self._client.stop()
                except Exception:
                    pass
                self._client = None

    async def _ensure_session(self, request: ApiMessageRequest) -> Any:
        signature = (request.model, request.system_prompt)

        async with self._lock:
            client = await self._ensure_client()
            if self._session is not None and self._session_signature == signature:
                return self._session

            if self._session is not None:
                try:
                    await self._session.disconnect()
                except Exception:
                    pass

            try:
                from copilot.types import PermissionRequestResult  # type: ignore[import-not-found]

                def _approve_all(*_args: Any, **_kwargs: Any) -> Any:
                    return PermissionRequestResult(kind="approved")

                self._session = await client.create_session(
                    model=request.model,
                    on_permission_request=_approve_all,
                    streaming=True,
                )
                self._session_signature = signature
            except Exception as exc:
                raise _translate_copilot_error(exc) from exc

            return self._session

    async def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from copilot import CopilotClient  # type: ignore[import-not-found]
        except Exception as exc:
            raise RequestFailure(
                "Copilot SDK não encontrado. Instale com: pip install github-copilot-sdk"
            ) from exc

        config: dict[str, Any] = {}
        if self._cli_path:
            config["cli_path"] = self._cli_path
        if self._cli_url:
            config["cli_url"] = self._cli_url
        if self._github_token:
            config["github_token"] = self._github_token

        try:
            self._client = CopilotClient(config or None)
            await self._client.start()
            return self._client
        except Exception as exc:
            raise _translate_copilot_error(exc) from exc

def _latest_user_prompt(messages: list[ConversationMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user" and message.text.strip():
            return message.text.strip()
    return ""


def _extract_response_text(response: Any) -> str:
    if response is None:
        return ""

    data = getattr(response, "data", None)
    if data is not None:
        content = getattr(data, "content", None)
        if isinstance(content, str):
            return content
        if content is not None:
            return str(content)

    if isinstance(response, str):
        return response
    return str(response)


def _translate_copilot_error(exc: Exception):
    message = str(exc).lower()
    if any(token in message for token in ("unauthorized", "forbidden", "token", "auth")):
        return AuthenticationFailure(str(exc))
    if "rate" in message and "limit" in message:
        return RateLimitFailure(str(exc))
    return RequestFailure(str(exc))


def _normalize_models(raw_models: Any) -> list[str]:
    if raw_models is None:
        return []
    if isinstance(raw_models, dict):
        candidate = raw_models.get("models")
        return _normalize_models(candidate)
    if not isinstance(raw_models, list):
        return []

    resolved: list[str] = []
    for item in raw_models:
        if isinstance(item, str):
            resolved.append(item)
            continue
        model_id = getattr(item, "id", None) or getattr(item, "name", None)
        if isinstance(model_id, str) and model_id:
            resolved.append(model_id)
            continue
        if isinstance(item, dict):
            dict_id = item.get("id") or item.get("name")
            if isinstance(dict_id, str) and dict_id:
                resolved.append(dict_id)
    return resolved


def _handle_session_event(
    event: Any,
    queue: asyncio.Queue[str],
    done: asyncio.Event,
    final_text_holder: dict[str, str],
) -> None:
    event_type = _event_type_value(event)
    data = getattr(event, "data", None)

    if event_type in {"assistant.message_delta", "assistant.reasoning_delta"}:
        delta = getattr(data, "delta_content", "") if data is not None else ""
        if delta:
            queue.put_nowait(str(delta))
        return

    if event_type in {"assistant.message", "assistant.reasoning"}:
        content = getattr(data, "content", "") if data is not None else ""
        if isinstance(content, str) and content:
            final_text_holder["value"] = content
        return

    if event_type == "session.idle":
        done.set()


def _event_type_value(event: Any) -> str:
    raw_type = getattr(event, "type", "")
    value = getattr(raw_type, "value", raw_type)
    return str(value)
