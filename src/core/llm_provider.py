"""
Multi-LLM Provider for CDP_Merged.
Ported from CDP's ai_service/llm_provider.py
Supports Ollama (local), OpenAI, and Azure OpenAI.
"""

import logging
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from src.config import settings
from src.core.azure_auth import AzureCredentialResolver

logger = logging.getLogger(__name__)


class LLMMode(StrEnum):
    """LLM provider modes."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    MOCK = "mock"


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate free-form text response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Any,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate structured output conforming to a Pydantic model."""
        pass


class OpenAIProvider(BaseLLMProvider):
    """Standard OpenAI provider."""

    def __init__(self, api_key: str, model: str = "gpt-5", base_url: str | None = None):
        try:
            from openai import AsyncOpenAI
        except ImportError as e:
            raise ImportError(
                "OpenAI dependencies not installed. Run: pip install openai>=1.10.0"
            ) from e

        self.api_key = api_key
        self.model = model

        if base_url:
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        else:
            self.client = AsyncOpenAI(api_key=api_key)
        logger.info(f"Initialized OpenAI provider: model={model}, base_url={base_url}")

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text using OpenAI."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Any,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate structured output using OpenAI native structured outputs."""
        try:
            response = await self.client.beta.chat.completions.parse(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                response_format=response_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.parsed
        except (ImportError, AttributeError, ValueError) as e:
            logger.error(f"OpenAI structured generation failed: {e}")
            raise


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI provider for cloud-hosted models."""

    def __init__(
        self,
        endpoint: str,
        deployment_name: str,
        api_version: str = "2024-02-01",
        api_key: str | None = None,
        azure_ad_token_provider: Any | None = None,
    ):
        try:
            from openai import AsyncAzureOpenAI
        except ImportError as e:
            raise ImportError(
                "Azure OpenAI dependencies not installed. Run: pip install openai>=1.10.0"
            ) from e

        if not api_key and azure_ad_token_provider is None:
            raise ValueError(
                "Azure OpenAI provider requires either API key or Azure AD token provider"
            )

        self.api_key = api_key
        self.endpoint = endpoint
        self.deployment_name = deployment_name
        self.api_version = api_version

        if azure_ad_token_provider is not None:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                azure_ad_token_provider=azure_ad_token_provider,
            )
        elif api_key:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
                api_key=api_key,
            )
        else:
            self.client = AsyncAzureOpenAI(
                azure_endpoint=endpoint,
                api_version=api_version,
            )
        logger.info(
            f"Initialized Azure OpenAI provider: deployment={deployment_name}, auth={'aad' if azure_ad_token_provider else 'api_key'}"
        )

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text using Azure OpenAI."""
        # GPT-5 compatibility: use max_completion_tokens, omit temperature
        kwargs: dict[str, Any] = {"model": self.deployment_name, "messages": messages}
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = max_tokens
        # GPT-5 only supports temperature=1 (default); omit for GPT-5
        if not self._is_gpt5():
            kwargs["temperature"] = temperature
        response = await self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def _is_gpt5(self) -> bool:
        """Check if the deployment is using GPT-5 model."""
        return self.deployment_name.lower().startswith("gpt-5")

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Any,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate structured output using Azure OpenAI."""
        try:
            # GPT-5 compatibility: use max_completion_tokens, omit temperature
            kwargs: dict[str, Any] = {
                "model": self.deployment_name,
                "messages": messages,
                "response_format": response_model,
            }
            if max_tokens is not None:
                kwargs["max_completion_tokens"] = max_tokens
            # GPT-5 only supports temperature=1 (default); omit for GPT-5
            if not self._is_gpt5():
                kwargs["temperature"] = temperature
            response = await self.client.beta.chat.completions.parse(**kwargs)
            return response.choices[0].message.parsed
        except (ImportError, AttributeError, ValueError) as e:
            logger.error(f"Azure OpenAI structured generation failed: {e}")
            raise


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local development."""

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "llama3.1:8b"):
        try:
            from ollama import AsyncClient
        except ImportError as e:
            raise ImportError(
                "Ollama dependencies not installed. Run: pip install ollama>=0.1.0"
            ) from e

        self.base_url = base_url
        self.model = model
        self.client = AsyncClient(host=base_url)
        logger.info(f"Initialized Ollama provider: url={base_url}, model={model}")

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text using Ollama."""
        response = await self.client.chat(
            model=self.model,
            messages=messages,
            stream=False,
            options={"temperature": temperature},
        )
        return response.get("message", {}).get("content", "")

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Any,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate structured output using Ollama tool calling."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "return_data",
                    "description": "Return structured data",
                    "parameters": response_model.model_json_schema(),
                },
            }
        ]

        response = await self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
            stream=False,
            options={"temperature": temperature},
        )

        # Parse tool call result
        message = response.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if not tool_calls:
            raise ValueError("No tool calls in Ollama response")

        tool_call = tool_calls[0]
        function_args = tool_call.get("function", {}).get("arguments", {})

        return response_model.model_validate(function_args)


class MockProvider(BaseLLMProvider):
    """Mock provider for testing without external dependencies."""

    def __init__(self):
        logger.info("Initialized Mock LLM provider")

    async def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate mock text response."""
        user_content = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                break
        return f"Mock response to: {user_content[:100]}"

    async def generate_structured(
        self,
        messages: list[dict[str, str]],
        response_model: Any,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate mock structured output."""
        # Return minimal valid instance
        try:
            return response_model()
        except (TypeError, ValueError):
            # If model requires fields, try with empty strings
            return response_model.model_construct()


def get_llm_provider() -> BaseLLMProvider:
    """
    Factory function to get the appropriate LLM provider based on configuration.
    """
    provider = settings.LLM_PROVIDER.lower()

    if provider == LLMMode.OPENAI:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider")
        return OpenAIProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.OPENAI_BASE_URL,
        )

    elif provider == LLMMode.AZURE_OPENAI:
        if not settings.AZURE_OPENAI_ENDPOINT:
            raise ValueError("AZURE_OPENAI_ENDPOINT is required for Azure OpenAI provider")
        if not settings.AZURE_OPENAI_DEPLOYMENT_NAME:
            raise ValueError("AZURE_OPENAI_DEPLOYMENT_NAME is required for Azure OpenAI provider")

        auth = AzureCredentialResolver("azure_openai").resolve(
            explicit_key=settings.AZURE_OPENAI_API_KEY,
            key_vault_secret_name=settings.AZURE_OPENAI_API_KEY_SECRET_NAME,
            token_scope="https://cognitiveservices.azure.com/.default",
            require_token_credential=False,
        )
        if not auth.api_key and auth.token_provider is None:
            raise ValueError(
                "Azure OpenAI authentication is not configured. "
                "Provide AZURE_OPENAI_API_KEY (or Key Vault secret) or enable managed identity"
            )

        return AzureOpenAIProvider(
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
            deployment_name=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            api_key=auth.api_key,
            azure_ad_token_provider=auth.token_provider,
        )

    elif provider == LLMMode.OLLAMA:
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.LLM_MODEL)

    elif provider == LLMMode.MOCK:
        return MockProvider()

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported: {', '.join([m.value for m in LLMMode])}"
        )
