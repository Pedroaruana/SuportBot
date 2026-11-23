import sys
import types

import pytest

from app.core.config import settings
from app.services import llm


def _fake_module(monkeypatch, name: str, cls_name: str):
    created: dict = {}

    class FakeChat:
        def __init__(self, **kwargs):
            created.update(kwargs)

    module = types.ModuleType(name)
    setattr(module, cls_name, FakeChat)
    monkeypatch.setitem(sys.modules, name, module)
    return created


def test_gemini_is_default(monkeypatch):
    created = _fake_module(monkeypatch, "langchain_google_genai", "ChatGoogleGenerativeAI")
    llm.build_llm()
    assert created["model"] == "gemini-2.5-flash-lite"
    assert created["google_api_key"] == settings.gemini_api_key


def test_openai_provider(monkeypatch):
    created = _fake_module(monkeypatch, "langchain_openai", "ChatOpenAI")
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "sk-teste")
    llm.build_llm()
    assert created["model"] == "gpt-4o-mini"
    assert created["api_key"] == "sk-teste"


def test_openai_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "openai_api_key", "")
    with pytest.raises(llm.LLMConfigError, match="OPENAI_API_KEY"):
        llm.build_llm()


def test_ollama_provider_with_custom_model(monkeypatch):
    created = _fake_module(monkeypatch, "langchain_ollama", "ChatOllama")
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_model", "qwen2.5")
    monkeypatch.setattr(settings, "ollama_base_url", "http://ollama:11434")
    llm.build_llm()
    assert created["model"] == "qwen2.5"
    assert created["base_url"] == "http://ollama:11434"


def test_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "claude-do-vizinho")
    with pytest.raises(llm.LLMConfigError, match="invalido"):
        llm.build_llm()


def test_missing_optional_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "langchain_ollama", None)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    with pytest.raises(llm.LLMConfigError, match="instale"):
        llm.build_llm()
