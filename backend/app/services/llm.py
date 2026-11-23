from functools import lru_cache
from importlib import import_module

from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import settings

DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash-lite",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
}
TEMPERATURE = 0.2


class LLMConfigError(RuntimeError):
    pass


def _load(module: str, package_hint: str):
    # Import tardio: so quem usa o provedor precisa instalar o pacote
    try:
        return import_module(module)
    except ImportError as e:
        raise LLMConfigError(f"Provedor indisponivel: instale com `pip install {package_hint}`.") from e


def _build_gemini(model: str) -> BaseChatModel:
    mod = _load("langchain_google_genai", "langchain-google-genai")
    return mod.ChatGoogleGenerativeAI(
        model=model,
        google_api_key=settings.gemini_api_key,
        temperature=TEMPERATURE,
        convert_system_message_to_human=True,
    )


def _build_openai(model: str) -> BaseChatModel:
    if not settings.openai_api_key:
        raise LLMConfigError("OPENAI_API_KEY nao configurada.")
    mod = _load("langchain_openai", "-r requirements-optional.txt")
    return mod.ChatOpenAI(model=model, api_key=settings.openai_api_key, temperature=TEMPERATURE)


def _build_ollama(model: str) -> BaseChatModel:
    mod = _load("langchain_ollama", "-r requirements-optional.txt")
    return mod.ChatOllama(model=model, base_url=settings.ollama_base_url, temperature=TEMPERATURE)


BUILDERS = {"gemini": _build_gemini, "openai": _build_openai, "ollama": _build_ollama}


def build_llm() -> BaseChatModel:
    provider = settings.llm_provider.strip().lower()
    builder = BUILDERS.get(provider)
    if builder is None:
        raise LLMConfigError(f"LLM_PROVIDER invalido: '{provider}'. Use: {', '.join(BUILDERS)}.")
    return builder(settings.llm_model or DEFAULT_MODELS[provider])


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    return build_llm()


def reset_llm_cache() -> None:
    get_llm.cache_clear()
