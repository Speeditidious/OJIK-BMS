"""LLM API client — supports OpenAI, Anthropic, Google Gemini, Ollama."""
from collections.abc import AsyncGenerator
from typing import Any

from app.core.config import settings

# Default model per provider
_DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
    "gemini": "gemini-2.0-flash",
    "ollama": settings.OLLAMA_MODEL,
}


class LLMClient:
    """Unified LLM client.

    Selects OpenAI / Anthropic / Gemini / Ollama based on the LLM_PROVIDER setting.
    Ollama is handled via its OpenAI-compatible endpoint using the same openai client.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._provider: str = settings.LLM_PROVIDER
        self._initialized = False

    async def initialize(self) -> None:
        """Lazily initialize the provider-specific client."""
        if self._initialized:
            return

        provider = self._provider

        if provider == "openai":
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        elif provider == "anthropic":
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        elif provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=settings.GOOGLE_API_KEY)
            model_name = settings.LLM_MODEL or _DEFAULT_MODELS["gemini"]
            self._client = genai.GenerativeModel(model_name)

        elif provider == "ollama":
            # Ollama exposes an OpenAI-compatible API — no extra package needed
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key="ollama",  # Ollama does not validate the API key
                base_url=f"{settings.OLLAMA_BASE_URL}/v1",
            )

        self._initialized = True

    @property
    def is_available(self) -> bool:
        provider = self._provider
        if provider == "openai":
            return bool(settings.OPENAI_API_KEY)
        if provider == "anthropic":
            return bool(settings.ANTHROPIC_API_KEY)
        if provider == "gemini":
            return bool(settings.GOOGLE_API_KEY)
        if provider == "ollama":
            return True  # Always available since it runs locally
        return False

    def _resolve_model(self, model: str | None) -> str:
        """Resolve the model name: explicit arg → LLM_MODEL setting → provider default."""
        return model or settings.LLM_MODEL or _DEFAULT_MODELS.get(self._provider, "")

    async def stream_chat(
        self,
        messages: list[dict],
        system_prompt: str | None = None,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion tokens.

        Args:
            messages: List of messages in [{"role": str, "content": str}, ...] format.
            system_prompt: Optional system prompt.
            model: Model name override; falls back to the provider default if omitted.
            max_tokens: Maximum number of tokens to generate.

        Yields:
            Token strings as they arrive.
        """
        await self.initialize()

        if not self.is_available:
            yield (
                f"LLM 설정 오류: LLM_PROVIDER='{self._provider}'에 맞는 API 키가 "
                "설정되지 않았습니다. .env 파일을 확인해주세요."
            )
            return

        resolved_model = self._resolve_model(model)

        if self._provider in ("openai", "ollama"):
            async for token in self._stream_openai_compatible(
                messages, system_prompt, resolved_model, max_tokens
            ):
                yield token

        elif self._provider == "anthropic":
            async for token in self._stream_anthropic(
                messages, system_prompt, resolved_model, max_tokens
            ):
                yield token

        elif self._provider == "gemini":
            async for token in self._stream_gemini(
                messages, system_prompt, max_tokens
            ):
                yield token

    async def _stream_openai_compatible(
        self,
        messages: list[dict],
        system_prompt: str | None,
        model: str,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens using the OpenAI-compatible API (OpenAI or Ollama)."""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        stream = await self._client.chat.completions.create(
            model=model,
            messages=all_messages,
            max_tokens=max_tokens,
            stream=True,
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def _stream_anthropic(
        self,
        messages: list[dict],
        system_prompt: str | None,
        model: str,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens using the Anthropic Claude API."""
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text

    async def _stream_gemini(
        self,
        messages: list[dict],
        system_prompt: str | None,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens using the Google Gemini API."""
        import asyncio

        # Gemini injects system_instruction at model creation time,
        # so a new model instance is created when system_prompt changes.
        import google.generativeai as genai

        model_name = self._resolve_model(None)
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system_prompt,
        )

        # Gemini history format: role must be "user" or "model"
        history = []
        for msg in messages[:-1]:
            history.append({
                "role": "model" if msg["role"] == "assistant" else "user",
                "parts": [msg["content"]],
            })
        last_message = messages[-1]["content"] if messages else ""

        chat = model.start_chat(history=history)
        response = await asyncio.to_thread(
            chat.send_message,
            last_message,
            generation_config={"max_output_tokens": max_tokens},
            stream=True,
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text

    async def get_embedding(self, text: str) -> list[float]:
        """Generate a text embedding vector.

        - OpenAI / Gemini: uses cloud API
        - Ollama: uses the nomic-embed-text model
        - Anthropic: embeddings not supported → raises RuntimeError
        """
        await self.initialize()

        if self._provider == "openai":
            response = await self._client.embeddings.create(
                input=text,
                model="text-embedding-3-small",
            )
            return response.data[0].embedding

        elif self._provider == "ollama":
            # Ollama exposes an OpenAI-compatible embeddings endpoint
            response = await self._client.embeddings.create(
                input=text,
                model="nomic-embed-text",  # ollama pull nomic-embed-text
            )
            return response.data[0].embedding

        elif self._provider == "gemini":
            import asyncio

            import google.generativeai as genai

            result = await asyncio.to_thread(
                genai.embed_content,
                model="models/text-embedding-004",
                content=text,
            )
            return result["embedding"]

        else:
            raise RuntimeError(
                f"Provider '{self._provider}' does not support embeddings. "
                "Use openai, gemini, or ollama instead."
            )


# Singleton instance
llm_client = LLMClient()
