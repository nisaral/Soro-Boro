"""Odyssey / LM Studio env selection. Never requires a live key."""

from __future__ import annotations

import os

from veyra.llm import default_llm_api_key, default_llm_base_url, make_llm


def test_lm_studio_fallback_when_odyssey_unset(monkeypatch):
    monkeypatch.delenv("ODYSSEY_API_KEY", raising=False)
    monkeypatch.delenv("ODYSSEY_BASE_URL", raising=False)
    assert default_llm_base_url() == "http://127.0.0.1:1234/v1"
    assert default_llm_api_key() in ("lm-studio", os.environ.get("OPENAI_API_KEY", "lm-studio"))


def test_odyssey_from_env(monkeypatch):
    monkeypatch.setenv("ODYSSEY_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ODYSSEY_BASE_URL", raising=False)
    assert default_llm_base_url() == "https://odysseyapi.tech/v1"
    assert default_llm_api_key() == "test-key-not-real"
    client = make_llm({"model_mode": "odyssey"})
    assert "odysseyapi.tech" in client.describe()
