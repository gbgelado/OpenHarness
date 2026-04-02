"""Provider detection/auth tests."""

from __future__ import annotations

from openharness.api.provider import auth_status, detect_provider
from openharness.config.settings import Settings


def test_detect_provider_explicit_copilot_sdk():
    settings = Settings(provider="copilot-sdk")
    info = detect_provider(settings)

    assert info.name == "copilot-sdk"
    assert info.auth_kind == "github_oauth_or_token"
    assert info.voice_supported is False


def test_auth_status_copilot_with_token():
    settings = Settings(provider="copilot-sdk", copilot_github_token="ghu_test")
    assert auth_status(settings) == "configured"


def test_auth_status_copilot_without_token(monkeypatch):
    monkeypatch.delenv("COPILOT_GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    settings = Settings(provider="copilot-sdk")
    assert auth_status(settings) == "cli-login-or-token"
