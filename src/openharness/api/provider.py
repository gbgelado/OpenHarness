"""Provider/auth capability helpers."""

from __future__ import annotations

from dataclasses import dataclass
import os

from openharness.config.settings import Settings


@dataclass(frozen=True)
class ProviderInfo:
    """Resolved provider metadata for UI and diagnostics."""

    name: str
    auth_kind: str
    voice_supported: bool
    voice_reason: str


def detect_provider(settings: Settings) -> ProviderInfo:
    """Infer the active provider and rough capability set."""
    configured_provider = settings.provider.lower().strip()
    if configured_provider in {"copilot", "copilot-sdk", "copilot_sdk"}:
        return ProviderInfo(
            name="copilot-sdk",
            auth_kind="github_oauth_or_token",
            voice_supported=False,
            voice_reason="voice mode is not wired for Copilot SDK in this build",
        )

    base_url = (settings.base_url or "").lower()
    model = settings.model.lower()
    if "moonshot" in base_url or model.startswith("kimi"):
        return ProviderInfo(
            name="moonshot-anthropic-compatible",
            auth_kind="api_key",
            voice_supported=False,
            voice_reason="voice mode requires a Claude.ai-style authenticated voice backend",
        )
    if "bedrock" in base_url:
        return ProviderInfo(
            name="bedrock-compatible",
            auth_kind="aws",
            voice_supported=False,
            voice_reason="voice mode is not wired for Bedrock in this build",
        )
    if "vertex" in base_url or "aiplatform" in base_url:
        return ProviderInfo(
            name="vertex-compatible",
            auth_kind="gcp",
            voice_supported=False,
            voice_reason="voice mode is not wired for Vertex in this build",
        )
    if base_url:
        return ProviderInfo(
            name="anthropic-compatible",
            auth_kind="api_key",
            voice_supported=False,
            voice_reason="voice mode currently requires a dedicated Claude.ai-style provider",
        )
    return ProviderInfo(
        name="anthropic",
        auth_kind="api_key",
        voice_supported=False,
        voice_reason="voice mode shell exists, but live voice auth/streaming is not configured in this build",
    )


def auth_status(settings: Settings) -> str:
    """Return a compact auth status string."""
    provider = settings.provider.lower().strip()
    if provider in {"copilot", "copilot-sdk", "copilot_sdk"}:
        if settings.copilot_github_token:
            return "configured"
        if os.environ.get("COPILOT_GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
            return "configured"
        return "cli-login-or-token"

    if settings.api_key:
        return "configured"
    return "missing"

