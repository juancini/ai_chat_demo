import pytest

from app.core.config import settings
from app.services.llm_service import MockLLMService, OpenRouterLLMService, get_llm_service


@pytest.mark.asyncio
async def test_mock_llm_service_response():
    service = MockLLMService()
    messages = [{"role": "user", "content": "Hello world"}]

    content, provider, model = await service.generate_response(messages)

    assert provider == "mock"
    assert model == "mock-demo-v1"
    assert "Hello world" in content
    assert "MOCK MODE ACTIVE" in content


@pytest.mark.asyncio
async def test_mock_llm_service_title_generation():
    service = MockLLMService()
    title = await service.generate_title("What is the capital of France?")

    assert title == "What is the capital of France?"


def test_get_llm_service_factory_fallback():
    # When OPENROUTER_API_KEY is None or empty, factory returns MockLLMService
    settings.OPENROUTER_API_KEY = None
    service = get_llm_service()
    assert isinstance(service, MockLLMService)


def test_get_llm_service_factory_openrouter():
    # When OPENROUTER_API_KEY is provided, factory returns OpenRouterLLMService
    settings.OPENROUTER_API_KEY = "sk-or-v1-testkey123"
    service = get_llm_service()
    assert isinstance(service, OpenRouterLLMService)
    settings.OPENROUTER_API_KEY = None  # reset
